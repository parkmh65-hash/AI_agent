import { Injectable, UnauthorizedException, BadRequestException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';
import * as bcrypt from 'bcrypt';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
  ) {}

  async signup(dto: { email: string; password?: string; name?: string; role?: string }) {
    const existing = await this.prisma.user.findUnique({ where: { email: dto.email } });
    if (existing) {
      throw new BadRequestException('이미 존재해 있는 이메일입니다.');
    }

    const passwordHash = dto.password ? await bcrypt.hash(dto.password, 10) : null;
    const user = await this.prisma.user.create({
      data: {
        email: dto.email,
        name: dto.name || '시민 사용자',
        passwordHash,
        role: dto.role || 'citizen',
      },
    });

    const tokens = this.generateTokens(user.id, user.email, user.role);
    return {
      message: '회원가입이 완료되었습니다.',
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
      ...tokens,
    };
  }

  async login(dto: { email: string; password?: string }) {
    const user = await this.prisma.user.findUnique({ where: { email: dto.email } });
    if (!user) {
      throw new UnauthorizedException('이메일 또는 비밀번호가 올바르지 않습니다.');
    }

    if (dto.password && user.passwordHash) {
      const isMatch = await bcrypt.compare(dto.password, user.passwordHash);
      if (!isMatch) {
        throw new UnauthorizedException('이메일 또는 비밀번호가 올바르지 않습니다.');
      }
    }

    const tokens = this.generateTokens(user.id, user.email, user.role);
    return {
      message: '로그인 성공',
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
      ...tokens,
    };
  }

  async adminLogin(dto: { email: string; password?: string }) {
    const res = await this.login(dto);
    if (res.user.role !== 'admin') {
      throw new UnauthorizedException('관리자 권한이 있는 계정만 로그인할 수 있습니다.');
    }
    return res;
  }

  async refresh(refreshToken: string) {
    try {
      const payload = this.jwtService.verify(refreshToken, {
        secret: process.env.JWT_REFRESH_SECRET || 'sejong-heritage-refresh-secret-2026',
      });
      const tokens = this.generateTokens(payload.sub, payload.email, payload.role);
      return tokens;
    } catch (e) {
      throw new UnauthorizedException('유효하지 않거나 만료된 리프레시 토큰입니다.');
    }
  }

  private generateTokens(userId: string, email: string, role: string) {
    const payload = { sub: userId, email, role };
    const accessToken = this.jwtService.sign(payload, {
      secret: process.env.JWT_SECRET || 'sejong-heritage-secret-key-2026',
      expiresIn: '1h',
    });
    const refreshToken = this.jwtService.sign(payload, {
      secret: process.env.JWT_REFRESH_SECRET || 'sejong-heritage-refresh-secret-2026',
      expiresIn: '7d',
    });

    return { accessToken, refreshToken };
  }
}
