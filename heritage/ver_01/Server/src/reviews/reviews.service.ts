import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface CreateReviewDto {
  userId?: string;
  courseId?: string;
  heritageId: string;
  rating?: number;
  companionType?: string;
  content?: string;
  isRecommended?: boolean;
  isPublic?: boolean;
  parkingAvailable?: boolean;
  parkingNote?: string;
  restroomAvailable?: boolean;
  restroomNote?: string;
  nearbyRestaurant?: boolean;
  imageUrls?: string[];
}

@Injectable()
export class ReviewsService {
  constructor(private prisma: PrismaService) {}

  async createReviews(input: CreateReviewDto | CreateReviewDto[]) {
    const list = Array.isArray(input) ? input : [input];
    const createdList = [];

    for (const dto of list) {
      // 만약 parkingNote나 restroomNote가 작성되었으면 해당 문화유산의 needsImprovement 플래그를 true로 변경
      if (dto.parkingNote || dto.restroomNote) {
        await this.prisma.heritage.update({
          where: { id: dto.heritageId },
          data: { needsImprovement: true },
        });
      }

      const review = await this.prisma.review.create({
        data: {
          userId: dto.userId || null,
          courseId: dto.courseId || null,
          heritageId: dto.heritageId,
          rating: dto.rating || 5,
          companionType: dto.companionType,
          content: dto.content,
          isRecommended: dto.isRecommended !== undefined ? dto.isRecommended : true,
          isPublic: dto.isPublic !== undefined ? dto.isPublic : true,
          parkingAvailable: dto.parkingAvailable,
          parkingNote: dto.parkingNote,
          restroomAvailable: dto.restroomAvailable,
          restroomNote: dto.restroomNote,
          nearbyRestaurant: dto.nearbyRestaurant,
          images: dto.imageUrls
            ? {
                create: dto.imageUrls.map((url) => ({ imageUrl: url })),
              }
            : undefined,
        },
        include: { images: true },
      });
      createdList.push(review);
    }

    return createdList;
  }

  async findByHeritage(heritageId: string) {
    return this.prisma.review.findMany({
      where: { heritageId, isPublic: true },
      orderBy: { createdAt: 'desc' },
      include: {
        user: { select: { id: true, name: true, email: true } },
        images: true,
      },
    });
  }
}
