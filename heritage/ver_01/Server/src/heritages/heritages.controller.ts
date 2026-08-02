import { Controller, Get, Post, Body, Param, Query, Req, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { HeritagesService } from './heritages.service';

@ApiTags('문화유산 현황 & 검색 API')
@Controller('heritages')
export class HeritagesController {
  constructor(private readonly heritagesService: HeritagesService) {}

  @ApiOperation({ summary: '문화유산 목록 (국가/지자체 또는 승인 시민제보)' })
  @Get()
  async findAll(
    @Query('source') source?: string,
    @Query('status') status?: string,
    @Query('page') page?: number,
    @Query('limit') limit?: number,
  ) {
    return this.heritagesService.findAll({ source, status, page, limit });
  }

  @ApiOperation({ summary: '시대별/읍면동별 통계 (그래프용)' })
  @Get('stats')
  async getStats(@Query('groupBy') groupBy: 'era' | 'dong') {
    return this.heritagesService.getStats(groupBy || 'era');
  }

  @ApiOperation({ summary: '실시간 총 개수' })
  @Get('count')
  async getCount(@Query('source') source?: string) {
    return this.heritagesService.getCount(source);
  }

  @ApiOperation({ summary: '통합 검색 (읍면동, 시대, 키워드)' })
  @Get('search')
  async search(
    @Query('q') q?: string,
    @Query('dong') dong?: string,
    @Query('sortBy') sortBy?: string,
  ) {
    return this.heritagesService.search({ q, dong, sortBy });
  }

  @ApiOperation({ summary: '인기 문화유산 (좋아요순)' })
  @Get('popular')
  async getPopular() {
    return this.heritagesService.getPopular();
  }

  @ApiOperation({ summary: '시민 제보 등록 (status=pending 생성)' })
  @Post('report')
  async createReport(
    @Body()
    dto: {
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
    },
  ) {
    return this.heritagesService.createReport(dto);
  }

  @ApiOperation({ summary: '상세 정보' })
  @Get(':id')
  async findOne(@Param('id') id: string) {
    return this.heritagesService.findOne(id);
  }

  @ApiOperation({ summary: '주변 문화유산 목록 (GPS 반경 검색)' })
  @Get(':id/nearby')
  async findNearby(@Param('id') id: string, @Query('radiusKm') radiusKm?: number) {
    return this.heritagesService.findNearby(id, radiusKm ? Number(radiusKm) : 5);
  }

  @ApiOperation({ summary: '시민 후기 요약 (평균 평점, 최근 후기 일부)' })
  @Get(':id/reviews/summary')
  async getReviewSummary(@Param('id') id: string) {
    return this.heritagesService.getReviewSummary(id);
  }

  @ApiOperation({ summary: '좋아요 토글' })
  @Post(':id/like')
  async toggleLike(@Param('id') id: string, @Body('userId') userId?: string) {
    return this.heritagesService.toggleLike(id, userId);
  }
}
