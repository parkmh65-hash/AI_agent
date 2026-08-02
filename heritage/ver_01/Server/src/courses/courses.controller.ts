import { Controller, Get, Post, Patch, Body, Param } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { CoursesService } from './courses.service';

@ApiTags('코스 만들기 API')
@Controller('courses')
export class CoursesController {
  constructor(private readonly coursesService: CoursesService) {}

  @ApiOperation({ summary: '선택된 heritageIds[]로 추천교통/총소요시간 계산' })
  @Post('draft/route')
  async calculateDraftRoute(@Body('heritageIds') heritageIds: string[]) {
    return this.coursesService.calculateDraftRoute(heritageIds || []);
  }

  @ApiOperation({ summary: '코스 저장 (course + course_items 생성)' })
  @Post()
  async createCourse(
    @Body()
    dto: {
      userId?: string;
      title?: string;
      heritageIds: string[];
      isPublic?: boolean;
    },
  ) {
    return this.coursesService.createCourse(dto);
  }

  @ApiOperation({ summary: '코스 상세 (지도용 좌표, 경로, 교통/시간 포함)' })
  @Get(':id')
  async findOne(@Param('id') id: string) {
    return this.coursesService.findOne(id);
  }

  @ApiOperation({ summary: '코스 수정 (항목 추가/제외, 이름 변경)' })
  @Patch(':id')
  async updateCourse(
    @Param('id') id: string,
    @Body() dto: { title?: string; heritageIds?: string[]; isPublic?: boolean },
  ) {
    return this.coursesService.updateCourse(id, dto);
  }

  @ApiOperation({ summary: 'is_public 전환 -> 홈 시민 추천 코스 노출' })
  @Patch(':id/publish')
  async publishCourse(
    @Param('id') id: string,
    @Body('isPublic') isPublic?: boolean,
  ) {
    return this.coursesService.publishCourse(id, isPublic !== undefined ? isPublic : true);
  }
}
