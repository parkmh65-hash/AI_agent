import { Test, TestingModule } from '@nestjs/testing';
import { HeritagesService } from './heritages.service';
import { PrismaService } from '../prisma/prisma.service';

describe('HeritagesService', () => {
  let service: HeritagesService;

  const mockPrisma = {
    heritage: {
      findMany: jest.fn(),
      count: jest.fn(),
      groupBy: jest.fn(),
      create: jest.fn(),
      findUnique: jest.fn(),
      update: jest.fn(),
    },
    review: {
      findMany: jest.fn(),
      aggregate: jest.fn(),
    },
    heritageLike: {
      findUnique: jest.fn(),
      delete: jest.fn(),
      create: jest.fn(),
    },
    $transaction: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        HeritagesService,
        { provide: PrismaService, useValue: mockPrisma },
      ],
    }).compile();

    service = module.get<HeritagesService>(HeritagesService);
  });

  it('should return paginated heritages', async () => {
    mockPrisma.heritage.findMany.mockResolvedValue([
      { id: 'h1', name: '비암사', source: 'registered', status: 'approved' },
    ]);
    mockPrisma.heritage.count.mockResolvedValue(1);

    const res = await service.findAll({ page: 1, limit: 10 });
    expect(res.items.length).toBe(1);
    expect(res.total).toBe(1);
  });

  it('should return stats grouped by era', async () => {
    mockPrisma.heritage.groupBy.mockResolvedValue([
      { era: '조선시대', _count: { id: 5 } },
    ]);

    const res = await service.getStats('era');
    expect(res).toEqual([{ key: '조선시대', count: 5 }]);
  });
});
