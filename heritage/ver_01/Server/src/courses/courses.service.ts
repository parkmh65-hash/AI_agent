import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { TransportService } from '../transport/transport.service';

@Injectable()
export class CoursesService {
  constructor(
    private prisma: PrismaService,
    private transportService: TransportService,
  ) {}

  async calculateDraftRoute(heritageIds: string[]) {
    const heritages = await this.prisma.heritage.findMany({
      where: { id: { in: heritageIds } },
    });

    // heritageIds 순서대로 정렬
    const sorted = heritageIds
      .map((id) => heritages.find((h) => h.id === id))
      .filter((h) => !!h);

    const routeInfo = await this.transportService.calculateRoute(sorted);
    return {
      heritageCount: sorted.length,
      heritages: sorted,
      ...routeInfo,
    };
  }

  async createCourse(dto: {
    userId?: string;
    title?: string;
    heritageIds: string[];
    isPublic?: boolean;
  }) {
    const route = await this.calculateDraftRoute(dto.heritageIds);

    const course = await this.prisma.course.create({
      data: {
        userId: dto.userId || null,
        title: dto.title || '세종시 문화유산 맞춤 코스',
        transportMode: route.transportMode,
        totalDurationMin: route.totalDurationMin,
        isPublic: dto.isPublic || false,
        courseItems: {
          create: dto.heritageIds.map((hId, idx) => ({
            heritageId: hId,
            sortOrder: idx + 1,
          })),
        },
      },
      include: {
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: { heritage: { include: { images: true } } },
        },
      },
    });

    return course;
  }

  async updateCourse(
    id: string,
    dto: { title?: string; heritageIds?: string[]; isPublic?: boolean },
  ) {
    const existing = await this.prisma.course.findUnique({ where: { id } });
    if (!existing) {
      throw new NotFoundException('해당 코스를 찾을 수 없습니다.');
    }

    let transportMode = existing.transportMode;
    let totalDurationMin = existing.totalDurationMin;

    if (dto.heritageIds && dto.heritageIds.length > 0) {
      const route = await this.calculateDraftRoute(dto.heritageIds);
      transportMode = route.transportMode;
      totalDurationMin = route.totalDurationMin;

      // 항목 재설정
      await this.prisma.courseItem.deleteMany({ where: { courseId: id } });
      await this.prisma.courseItem.createMany({
        data: dto.heritageIds.map((hId, idx) => ({
          courseId: id,
          heritageId: hId,
          sortOrder: idx + 1,
        })),
      });
    }

    const updated = await this.prisma.course.update({
      where: { id },
      data: {
        title: dto.title !== undefined ? dto.title : existing.title,
        isPublic: dto.isPublic !== undefined ? dto.isPublic : existing.isPublic,
        transportMode,
        totalDurationMin,
      },
      include: {
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: { heritage: { include: { images: true } } },
        },
      },
    });

    return updated;
  }

  async publishCourse(id: string, isPublic = true) {
    const course = await this.prisma.course.findUnique({ where: { id } });
    if (!course) {
      throw new NotFoundException('해당 코스를 찾을 수 없습니다.');
    }
    return this.prisma.course.update({
      where: { id },
      data: { isPublic },
    });
  }

  async findOne(id: string) {
    const course = await this.prisma.course.findUnique({
      where: { id },
      include: {
        user: { select: { id: true, name: true, email: true } },
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: { heritage: { include: { images: true } } },
        },
        magazines: { orderBy: { createdAt: 'desc' } },
      },
    });

    if (!course) {
      throw new NotFoundException('해당 코스를 찾을 수 없습니다.');
    }

    const sortedHeritages = course.courseItems.map((ci) => ci.heritage);
    const route = await this.transportService.calculateRoute(sortedHeritages);

    return {
      ...course,
      route,
    };
  }
}
