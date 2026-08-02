import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class HeritagesService {
  constructor(private prisma: PrismaService) {}

  async findAll(query: { source?: string; status?: string; page?: number; limit?: number }) {
    const page = Number(query.page) || 1;
    const limit = Number(query.limit) || 20;
    const skip = (page - 1) * limit;

    const where: any = {};
    if (query.source) where.source = query.source;
    if (query.status) {
      where.status = query.status;
    } else if (query.source === 'citizen') {
      where.status = 'approved';
    }

    const [items, total] = await Promise.all([
      this.prisma.heritage.findMany({
        where,
        skip,
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: { images: true },
      }),
      this.prisma.heritage.count({ where }),
    ]);

    return {
      items,
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    };
  }

  async getStats(groupBy: 'era' | 'dong') {
    if (groupBy === 'era') {
      const result = await this.prisma.heritage.groupBy({
        by: ['era'],
        _count: { id: true },
        where: { status: 'approved' },
      });
      return result.map((r) => ({
        key: r.era || '기타/미정',
        count: r._count.id,
      }));
    } else {
      const result = await this.prisma.heritage.groupBy({
        by: ['dong'],
        _count: { id: true },
        where: { status: 'approved' },
      });
      return result.map((r) => ({
        key: r.dong || '세종특별자치시 전체',
        count: r._count.id,
      }));
    }
  }

  async getCount(source?: string) {
    const where: any = {};
    if (source) {
      where.source = source;
      if (source === 'citizen') where.status = 'approved';
    }
    const count = await this.prisma.heritage.count({ where });
    return { source: source || 'all', count };
  }

  async createReport(dto: {
    name: string;
    era?: string;
    dong?: string;
    latitude?: number;
    longitude?: number;
    description?: string;
    thinkingPoint?: string;
    reportReason?: string;
    reportedById?: string;
    imageUrls?: string[];
  }) {
    const heritage = await this.prisma.heritage.create({
      data: {
        name: dto.name,
        era: dto.era || '지방등록/시민발굴',
        dong: dto.dong || '조치원읍',
        latitude: dto.latitude,
        longitude: dto.longitude,
        description: dto.description,
        thinkingPoint: dto.thinkingPoint,
        source: 'citizen',
        status: 'pending',
        reportedById: dto.reportedById || null,
        reportReason: dto.reportReason,
        images: dto.imageUrls
          ? {
              create: dto.imageUrls.map((url, idx) => ({
                imageUrl: url,
                sortOrder: idx,
              })),
            }
          : undefined,
      },
      include: { images: true },
    });
    return heritage;
  }

  async search(query: { q?: string; dong?: string; sortBy?: string }) {
    const where: any = { status: 'approved' };
    if (query.q) {
      where.OR = [
        { name: { contains: query.q } },
        { description: { contains: query.q } },
        { era: { contains: query.q } },
      ];
    }
    if (query.dong) {
      where.dong = { contains: query.dong };
    }

    let orderBy: any = { createdAt: 'desc' };
    if (query.sortBy === 'popular' || query.sortBy === 'likeCount') {
      orderBy = { likeCount: 'desc' };
    } else if (query.sortBy === 'name') {
      orderBy = { name: 'asc' };
    }

    return this.prisma.heritage.findMany({
      where,
      orderBy,
      include: { images: true },
    });
  }

  async getPopular() {
    return this.prisma.heritage.findMany({
      where: { status: 'approved' },
      orderBy: { likeCount: 'desc' },
      take: 10,
      include: { images: true },
    });
  }

  async findOne(id: string) {
    const heritage = await this.prisma.heritage.findUnique({
      where: { id },
      include: {
        images: { orderBy: { sortOrder: 'asc' } },
        reportedBy: { select: { id: true, name: true, email: true } },
      },
    });
    if (!heritage) {
      throw new NotFoundException('해당 문화유산을 찾을 수 없습니다.');
    }
    return heritage;
  }

  async findNearby(id: string, radiusKm = 5) {
    const current = await this.findOne(id);
    if (!current.latitude || !current.longitude) {
      return [];
    }

    const all = await this.prisma.heritage.findMany({
      where: {
        id: { not: id },
        status: 'approved',
        latitude: { not: null },
        longitude: { not: null },
      },
      include: { images: true },
    });

    return all
      .map((h) => {
        const dist = this.calculateDistance(
          current.latitude,
          current.longitude,
          h.latitude,
          h.longitude,
        );
        return { ...h, distanceKm: Math.round(dist * 100) / 100 };
      })
      .filter((h) => h.distanceKm <= radiusKm)
      .sort((a, b) => a.distanceKm - b.distanceKm);
  }

  async getReviewSummary(id: string) {
    const reviews = await this.prisma.review.findMany({
      where: { heritageId: id, isPublic: true },
      orderBy: { createdAt: 'desc' },
      take: 5,
      include: {
        user: { select: { id: true, name: true } },
        images: true,
      },
    });

    const avg = await this.prisma.review.aggregate({
      where: { heritageId: id, isPublic: true },
      _avg: { rating: true },
      _count: { id: true },
    });

    return {
      heritageId: id,
      averageRating: Math.round((avg._avg.rating || 0) * 10) / 10,
      totalReviewCount: avg._count.id,
      recentReviews: reviews,
    };
  }

  async toggleLike(id: string, userId?: string) {
    const heritage = await this.findOne(id);

    if (userId) {
      const existingLike = await this.prisma.heritageLike.findUnique({
        where: {
          heritageId_userId: {
            heritageId: id,
            userId,
          },
        },
      });

      if (existingLike) {
        await this.prisma.$transaction([
          this.prisma.heritageLike.delete({ where: { id: existingLike.id } }),
          this.prisma.heritage.update({
            where: { id },
            data: { likeCount: { decrement: 1 } },
          }),
        ]);
        return { liked: false, likeCount: Math.max(0, heritage.likeCount - 1) };
      } else {
        await this.prisma.$transaction([
          this.prisma.heritageLike.create({
            data: { heritageId: id, userId },
          }),
          this.prisma.heritage.update({
            where: { id },
            data: { likeCount: { increment: 1 } },
          }),
        ]);
        return { liked: true, likeCount: heritage.likeCount + 1 };
      }
    } else {
      const updated = await this.prisma.heritage.update({
        where: { id },
        data: { likeCount: { increment: 1 } },
      });
      return { liked: true, likeCount: updated.likeCount };
    }
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }
}
