import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';

describe('Sejong Heritage API (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
  });

  afterAll(async () => {
    if (app) {
      await app.close();
    }
  });

  describe('1. Auth Domain', () => {
    it('POST /auth/signup - creates a user', async () => {
      const email = `testuser_${Date.now()}@sejong.kr`;
      const res = await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email, password: 'password123', name: '테스트 유저' })
        .expect(201);

      expect(res.body.user).toBeDefined();
      expect(res.body.user.email).toBe(email);
      expect(res.body.accessToken).toBeDefined();
    });

    it('POST /auth/login - logs in user', async () => {
      const email = `loginuser_${Date.now()}@sejong.kr`;
      await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email, password: 'password123', name: '로그인 유저' })
        .expect(201);

      const res = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email, password: 'password123' })
        .expect(201);

      expect(res.body.accessToken).toBeDefined();
    });
  });

  describe('2. Home Domain', () => {
    it('GET /home/summary - returns count summary', async () => {
      const res = await request(app.getHttpServer()).get('/home/summary').expect(200);
      expect(res.body.registeredCount).toBeDefined();
      expect(res.body.citizenCount).toBeDefined();
    });

    it('GET /home/featured - returns featured heritages', async () => {
      const res = await request(app.getHttpServer()).get('/home/featured').expect(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    it('GET /home/public-courses - returns public courses', async () => {
      const res = await request(app.getHttpServer()).get('/home/public-courses').expect(200);
      expect(Array.isArray(res.body)).toBe(true);
    });
  });

  describe('3. Heritages Domain', () => {
    it('GET /heritages - returns list', async () => {
      const res = await request(app.getHttpServer()).get('/heritages').expect(200);
      expect(res.body.items).toBeDefined();
    });

    it('GET /heritages/stats?groupBy=era - returns era stats', async () => {
      const res = await request(app.getHttpServer())
        .get('/heritages/stats?groupBy=era')
        .expect(200);
      expect(Array.isArray(res.body)).toBe(true);
    });

    it('POST /heritages/report - creates a citizen report (pending)', async () => {
      const res = await request(app.getHttpServer())
        .post('/heritages/report')
        .send({
          name: '신규 시민 제보 문화유산',
          dong: '조치원읍',
          description: '시민 제보 설명',
          reportReason: '역사적 가치가 큽니다.',
        })
        .expect(201);

      expect(res.body.id).toBeDefined();
      expect(res.body.status).toBe('pending');
    });
  });

  describe('4. Courses & Transport Domain', () => {
    it('POST /courses/draft/route - calculates route info', async () => {
      const res = await request(app.getHttpServer())
        .post('/courses/draft/route')
        .send({ heritageIds: [] })
        .expect(201);

      expect(res.body.transportMode).toBeDefined();
      expect(res.body.totalDurationMin).toBeDefined();
    });
  });
});
