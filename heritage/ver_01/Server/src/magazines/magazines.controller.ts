import { Controller, Post, Param, Body } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { MagazinesService } from './magazines.service';

@ApiTags('AI 여행잡지 API')
@Controller('courses')
export class MagazinesController {
  constructor(private readonly magazinesService: MagazinesService) {}

  @ApiOperation({ summary: 'AI 여행잡지 생성 (Claude API 호출 -> HTML/PDF 생성)' })
  @Post(':id/magazine')
  async generateMagazine(@Param('id') id: string) {
    return this.magazinesService.generateMagazine(id);
  }

  @ApiOperation({ summary: '생성된 여행잡지를 입력 이메일로 발송' })
  @Post(':id/magazine/send')
  async sendMagazine(
    @Param('id') id: string,
    @Body('email') email: string,
  ) {
    return this.magazinesService.sendMagazine(id, email);
  }
}
