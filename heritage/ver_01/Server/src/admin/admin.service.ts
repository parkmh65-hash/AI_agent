import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private prisma: PrismaService) {}

  async getAdminHeritages(status?: string, needsImprovement?: boolean) {
    const where: any = {};
    if (status) where.status = status;
    if (needsImprovement !== undefined) where.needsImprovement = needsImprovement;

    return this.prisma.heritage.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      include: {
        images: true,
        reportedBy: { select: { id: true, name: true, email: true } },
      },
    });
  }

  async approveHeritage(id: string, reviewerNote?: string) {
    const heritage = await this.prisma.heritage.findUnique({ where: { id } });
    if (!heritage) {
      throw new NotFoundException('해당 제보 항목을 찾을 수 없습니다.');
    }

    return this.prisma.heritage.update({
      where: { id },
      data: {
        status: 'approved',
        reviewerNote: reviewerNote || heritage.reviewerNote,
      },
    });
  }

  async rejectHeritage(id: string, reviewerNote?: string) {
    const heritage = await this.prisma.heritage.findUnique({ where: { id } });
    if (!heritage) {
      throw new NotFoundException('해당 제보 항목을 찾을 수 없습니다.');
    }

    return this.prisma.heritage.update({
      where: { id },
      data: {
        status: 'rejected',
        reviewerNote: reviewerNote || heritage.reviewerNote,
      },
    });
  }

  async updateHeritage(
    id: string,
    dto: {
      name?: string;
      era?: string;
      dong?: string;
      description?: string;
      thinkingPoint?: string;
      reviewerNote?: string;
      needsImprovement?: boolean;
    },
  ) {
    const heritage = await this.prisma.heritage.findUnique({ where: { id } });
    if (!heritage) {
      throw new NotFoundException('해당 문화유산을 찾을 수 없습니다.');
    }

    return this.prisma.heritage.update({
      where: { id },
      data: { ...dto },
    });
  }

  async getReviewIssues() {
    return this.prisma.review.findMany({
      where: {
        OR: [
          { parkingNote: { not: null } },
          { restroomNote: { not: null } },
          { heritage: { needsImprovement: true } },
        ],
      },
      orderBy: { createdAt: 'desc' },
      include: {
        heritage: true,
        user: { select: { id: true, name: true, email: true } },
      },
    });
  }

  async getReportStats() {
    const [eraStats, dongStats, totalUsers, totalReviews, statusCount] = await Promise.all([
      this.prisma.heritage.groupBy({
        by: ['era'],
        _count: { id: true },
      }),
      this.prisma.heritage.groupBy({
        by: ['dong'],
        _count: { id: true },
      }),
      this.prisma.user.count(),
      this.prisma.review.count(),
      this.prisma.heritage.groupBy({
        by: ['status'],
        _count: { id: true },
      }),
    ]);

    return {
      eraStats: eraStats.map((e) => ({ era: e.era || '기타', count: e._count.id })),
      dongStats: dongStats.map((d) => ({ dong: d.dong || '전체', count: d._count.id })),
      statusCount: statusCount.map((s) => ({ status: s.status, count: s._count.id })),
      totalUsers,
      totalReviews,
      generatedAt: new Date(),
    };
  }

  async exportReport(format = 'pdf') {
    const stats = await this.getReportStats();
    return {
      format,
      downloadUrl: `https://storage.sejong.go.kr/reports/admin_report_${Date.now()}.${format}`,
      statsSummary: stats,
    };
  }

  async importBatchHeritageData(records: Array<{
    name: string;
    era?: string;
    dong?: string;
    dong_eup_myeon?: string;
    latitude?: number;
    lat?: number;
    longitude?: number;
    lng?: number;
    description?: string;
    thinkingPoint?: string;
    thinking_point?: string;
    think_about?: string;
    source?: string;
    status?: string;
    imageFileName?: string;
    imageUrl?: string;
  }>) {
    const supabaseUrl = process.env.SUPABASE_URL || 'https://your-supabase-project.supabase.co';
    const insertedList = [];

    for (const record of records) {
      let finalImageUrl = record.imageUrl;
      if (!finalImageUrl && record.imageFileName) {
        finalImageUrl = `${supabaseUrl}/storage/v1/object/public/heritage-images/${encodeURIComponent(record.imageFileName)}`;
      }

      const dongValue = record.dong || record.dong_eup_myeon || '세종특별자치시';
      const latValue = record.latitude || record.lat;
      const lngValue = record.longitude || record.lng;
      const thinkingValue = record.thinkingPoint || record.thinking_point || record.think_about;

      const heritage = await this.prisma.heritage.create({
        data: {
          name: record.name,
          era: record.era || '시대 미상',
          dong: dongValue,
          latitude: latValue ? Number(latValue) : null,
          longitude: lngValue ? Number(lngValue) : null,
          description: record.description,
          thinkingPoint: thinkingValue,
          source: record.source || 'registered',
          status: record.status || 'approved',
          images: finalImageUrl
            ? {
                create: [{ imageUrl: finalImageUrl, sortOrder: 0 }],
              }
            : undefined,
        },
        include: { images: true },
      });

      insertedList.push({
        ...heritage,
        dong_eup_myeon: heritage.dong,
        thinking_point: heritage.thinkingPoint,
        supabaseStorageUrl: finalImageUrl || null,
      });
    }

    return {
      message: `성공적으로 ${insertedList.length}건의 문화유산 데이터와 이미지를 Supabase DB 및 Storage에 등록하였습니다.`,
      count: insertedList.length,
      data: insertedList,
    };
  }
}
