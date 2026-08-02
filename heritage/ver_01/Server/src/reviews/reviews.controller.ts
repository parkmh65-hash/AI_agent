import { Controller, Get, Post, Body, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { ReviewsService, CreateReviewDto } from './reviews.service';

@ApiTags('후기 API')
@Controller('reviews')
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  @ApiOperation({ summary: '코스 내 문화유산별 후기 등록 (단일 또는 배열 일괄 등록)' })
  @Post()
  async createReviews(@Body() dto: CreateReviewDto | CreateReviewDto[]) {
    return this.reviewsService.createReviews(dto);
  }

  @ApiOperation({ summary: '특정 문화유산 후기 목록' })
  @Get()
  async findByHeritage(@Query('heritageId') heritageId: string) {
    return this.reviewsService.findByHeritage(heritageId);
  }
}
