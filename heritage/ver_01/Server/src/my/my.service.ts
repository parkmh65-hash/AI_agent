import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class MyService {
  constructor(private prisma: PrismaService) {}

  async getMyCourses(userId?: string) {
    if (!userId) return [];
    return this.prisma.course.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      include: {
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: { heritage: { include: { images: true } } },
        },
      },
    });
  }

  async getMyReports(userId?: string) {
    if (!userId) return [];
    return this.prisma.heritage.findMany({
      where: { reportedById: userId },
      orderBy: { createdAt: 'desc' },
      include: { images: true },
    });
  }
}
