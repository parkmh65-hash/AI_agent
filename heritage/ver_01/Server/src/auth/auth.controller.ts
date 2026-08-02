import { Controller, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { AuthService } from './auth.service';

@ApiTags('인증 API')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @ApiOperation({ summary: '일반 사용자 가입' })
  @Post('signup')
  async signup(@Body() dto: { email: string; password?: string; name?: string }) {
    return this.authService.signup(dto);
  }

  @ApiOperation({ summary: '로그인 (JWT 발급)' })
  @Post('login')
  async login(@Body() dto: { email: string; password?: string }) {
    return this.authService.login(dto);
  }

  @ApiOperation({ summary: '토큰 갱신' })
  @Post('refresh')
  async refresh(@Body() dto: { refreshToken: string }) {
    return this.authService.refresh(dto.refreshToken);
  }

  @ApiOperation({ summary: '관리자 로그인 (role=admin 검증)' })
  @Post('admin/login')
  async adminLogin(@Body() dto: { email: string; password?: string }) {
    return this.authService.adminLogin(dto);
  }
}
