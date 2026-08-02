import { Test, TestingModule } from '@nestjs/testing';
import { CoursesService } from './courses.service';
import { PrismaService } from '../prisma/prisma.service';
import { TransportService } from '../transport/transport.service';

describe('CoursesService', () => {
  let service: CoursesService;

  const mockPrisma = {
    heritage: {
      findMany: jest.fn(),
    },
    course: {
      create: jest.fn(),
      findUnique: jest.fn(),
      update: jest.fn(),
    },
    courseItem: {
      deleteMany: jest.fn(),
      createMany: jest.fn(),
    },
  };

  const mockTransport = {
    calculateRoute: jest.fn().mockResolvedValue({
      transportMode: '도보',
      totalDurationMin: 60,
      totalDistanceKm: 2,
      sections: [],
    }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CoursesService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: TransportService, useValue: mockTransport },
      ],
    }).compile();

    service = module.get<CoursesService>(CoursesService);
  });

  it('should calculate draft route correctly', async () => {
    mockPrisma.heritage.findMany.mockResolvedValue([
      { id: 'h1', name: '비암사', latitude: 36.6, longitude: 127.1 },
    ]);

    const res = await service.calculateDraftRoute(['h1']);
    expect(res.transportMode).toBe('도보');
    expect(res.totalDurationMin).toBe(60);
  });
});
