import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class HomeService {
  constructor(private prisma: PrismaService) {}

  async getSummary() {
    const registeredCount = await this.prisma.heritage.count({
      where: { source: 'registered' },
    });
    const citizenCount = await this.prisma.heritage.count({
      where: { source: 'citizen', status: 'approved' },
    });
    const totalCourses = await this.prisma.course.count({
      where: { isPublic: true },
    });

    return {
      registeredCount,
      citizenCount,
      totalCount: registeredCount + citizenCount,
      publicCourseCount: totalCourses,
      updatedAt: new Date(),
    };
  }

  async getFeatured() {
    return this.prisma.heritage.findMany({
      where: { status: 'approved' },
      orderBy: { likeCount: 'desc' },
      take: 6,
      include: {
        images: true,
      },
    });
  }

  async getPublicCourses() {
    return this.prisma.course.findMany({
      where: { isPublic: true },
      orderBy: { createdAt: 'desc' },
      take: 10,
      include: {
        user: { select: { id: true, name: true, email: true } },
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: {
            heritage: {
              include: { images: true },
            },
          },
        },
      },
    });
  }

  async getRecommended(userId?: string) {
    // 1차 범위 제외, 인터페이스 확보용
    const popularCourses = await this.getPublicCourses();
    return {
      userId: userId || null,
      message: '사용자 취향 기반 맞춤 문화유산 코스 추천 인터페이스',
      recommendations: popularCourses,
    };
  }
}
