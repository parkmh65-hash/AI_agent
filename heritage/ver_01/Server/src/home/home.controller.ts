import { Controller, Get, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { HomeService } from './home.service';

@ApiTags('홈 / 요약 API')
@Controller('home')
export class HomeController {
  constructor(private readonly homeService: HomeService) {}

  @ApiOperation({ summary: '국가/지자체 건수, 시민문화유산 건수 실시간 카운트' })
  @Get('summary')
  async getSummary() {
    return this.homeService.getSummary();
  }

  @ApiOperation({ summary: '이달의 세종시 대표 문화유산 목록' })
  @Get('featured')
  async getFeatured() {
    return this.homeService.getFeatured();
  }

  @ApiOperation({ summary: '시민 추천 문화유산 코스 목록' })
  @Get('public-courses')
  async getPublicCourses() {
    return this.homeService.getPublicCourses();
  }

  @ApiOperation({ summary: '내게 맞는 문화유산 코스 추천 (인터페이스)' })
  @Get('recommended')
  async getRecommended(@Query('userId') userId?: string) {
    return this.homeService.getRecommended(userId);
  }
}
