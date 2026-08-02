import { Test, TestingModule } from '@nestjs/testing';
import { AuthService } from './auth.service';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';

describe('AuthService', () => {
  let service: AuthService;
  let prisma: PrismaService;

  const mockPrisma = {
    user: {
      findUnique: jest.fn(),
      create: jest.fn(),
    },
  };

  const mockJwtService = {
    sign: jest.fn().mockReturnValue('mock_token'),
    verify: jest.fn().mockReturnValue({ sub: 'user-id', email: 'test@sejong.kr', role: 'citizen' }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: JwtService, useValue: mockJwtService },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    prisma = module.get<PrismaService>(PrismaService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  it('should signup a new user successfully', async () => {
    mockPrisma.user.findUnique.mockResolvedValue(null);
    mockPrisma.user.create.mockResolvedValue({
      id: 'uuid-1',
      email: 'new@sejong.kr',
      name: '신규유저',
      role: 'citizen',
    });

    const result = await service.signup({
      email: 'new@sejong.kr',
      password: 'password123',
      name: '신규유저',
    });

    expect(result.message).toBe('회원가입이 완료되었습니다.');
    expect(result.accessToken).toBe('mock_token');
  });

  it('should login an existing user', async () => {
    mockPrisma.user.findUnique.mockResolvedValue({
      id: 'uuid-1',
      email: 'existing@sejong.kr',
      name: '기존유저',
      role: 'citizen',
      passwordHash: null,
    });

    const result = await service.login({ email: 'existing@sejong.kr' });
    expect(result.accessToken).toBe('mock_token');
  });
});
