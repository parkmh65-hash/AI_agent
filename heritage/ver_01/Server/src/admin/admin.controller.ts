import { Controller, Get, Patch, Post, Param, Query, Body, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AdminService } from './admin.service';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { RolesGuard } from '../auth/roles.guard';
import { Roles } from '../auth/roles.decorator';

@ApiTags('관리자 API')
@Controller('admin')
export class AdminController {
  constructor(private readonly adminService: AdminService) {}

  @ApiOperation({ summary: '시민 제보 및 관리자 문화유산 조회 (status=pending, needsImprovement 등)' })
  @Get('heritages')
  async getAdminHeritages(
    @Query('status') status?: string,
    @Query('needsImprovement') needsImprovement?: string,
  ) {
    const isNeedsImp = needsImprovement !== undefined ? needsImprovement === 'true' : undefined;
    return this.adminService.getAdminHeritages(status, isNeedsImp);
  }

  @ApiOperation({ summary: '승인 처리 (status=approved, 시민 목록 노출)' })
  @Patch('heritages/:id/approve')
  async approveHeritage(
    @Param('id') id: string,
    @Body('reviewerNote') reviewerNote?: string,
  ) {
    return this.adminService.approveHeritage(id, reviewerNote);
  }

  @ApiOperation({ summary: '반려 처리 (status=rejected)' })
  @Patch('heritages/:id/reject')
  async rejectHeritage(
    @Param('id') id: string,
    @Body('reviewerNote') reviewerNote?: string,
  ) {
    return this.adminService.rejectHeritage(id, reviewerNote);
  }

  @ApiOperation({ summary: '검토 수정 (승인/제보 항목 데이터 수정)' })
  @Patch('heritages/:id')
  async updateHeritage(
    @Param('id') id: string,
    @Body()
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
    return this.adminService.updateHeritage(id, dto);
  }

  @ApiOperation({ summary: '시민 후기 중 개선필요 편의사항 모아보기' })
  @Get('reviews/issues')
  async getReviewIssues() {
    return this.adminService.getReviewIssues();
  }

  @ApiOperation({ summary: '통계 보고서 데이터 (그래프용 집계)' })
  @Get('reports')
  async getReportStats() {
    return this.adminService.getReportStats();
  }

  @ApiOperation({ summary: '보고서 파일 (PDF/Excel) 생성' })
  @Post('reports/export')
  async exportReport(@Body('format') format?: string) {
    return this.adminService.exportReport(format || 'pdf');
  }

  @ApiOperation({ summary: '외부 엑셀 데이터 및 이미지 일괄 파싱/업로드 (Supabase DB & Storage 연동)' })
  @Post('import-excel')
  async importExcelData(
    @Body('records')
    records: Array<{
      name: string;
      era?: string;
      dong?: string;
      latitude?: number;
      longitude?: number;
      description?: string;
      thinkingPoint?: string;
      source?: string;
      status?: string;
      imageFileName?: string;
      imageUrl?: string;
    }>,
  ) {
    return this.adminService.importBatchHeritageData(records || []);
  }
}
