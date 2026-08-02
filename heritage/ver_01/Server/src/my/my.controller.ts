import { Controller, Get, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { MyService } from './my.service';

@ApiTags('나만의 문화유산 API')
@Controller('my')
export class MyController {
  constructor(private readonly myService: MyService) {}

  @ApiOperation({ summary: '내가 저장한 코스 목록' })
  @Get('courses')
  async getMyCourses(@Query('userId') userId?: string) {
    return this.myService.getMyCourses(userId);
  }

  @ApiOperation({ summary: '내가 제보한 문화유산 목록 + 승인 상태' })
  @Get('reports')
  async getMyReports(@Query('userId') userId?: string) {
    return this.myService.getMyReports(userId);
  }
}
