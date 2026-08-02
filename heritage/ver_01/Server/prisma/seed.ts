import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Starting Sejong Heritage Database Seeding...');

  // 1. Create Admin & Citizen Users
  const adminPassword = await bcrypt.hash('admin1234', 10);
  const citizenPassword = await bcrypt.hash('citizen1234', 10);

  const adminUser = await prisma.user.upsert({
    where: { email: 'admin@sejong.go.kr' },
    update: {},
    create: {
      email: 'admin@sejong.go.kr',
      name: '세종시 관리자',
      role: 'admin',
      passwordHash: adminPassword,
    },
  });

  const citizenUser = await prisma.user.upsert({
    where: { email: 'citizen@sejong.kr' },
    update: {},
    create: {
      email: 'citizen@sejong.kr',
      name: '김세종',
      role: 'citizen',
      passwordHash: citizenPassword,
    },
  });

  console.log(`👤 Users seeded: Admin (${adminUser.id}), Citizen (${citizenUser.id})`);

  // 2. Create Registered Heritages
  const biamsa = await prisma.heritage.create({
    data: {
      name: '세종 비암사 (극락보전)',
      era: '통일신라/고려',
      dong: '전의면',
      latitude: 36.6488,
      longitude: 127.1895,
      description: '통일신라 시대 삼의사가 창건했다고 전해지며 삼국시대 계유명전씨아미타불비상(국보 제106호)이 발견된 천년고찰입니다.',
      thinkingPoint: '천년 전 백제와 신라의 유민들이 비암사에서 불상을 조성하며 빌었던 염원은 무엇이었을까요?',
      source: 'registered',
      status: 'approved',
      likeCount: 42,
      naverMapUrl: 'https://map.naver.com/v5/search/비암사',
      googleMapUrl: 'https://maps.google.com/?q=36.6488,127.1895',
      images: {
        create: [
          {
            imageUrl: 'https://images.unsplash.com/photo-1548625149-fc4a29cf7092?auto=format&fit=crop&w=800&q=80',
            sortOrder: 0,
          },
        ],
      },
    },
  });

  const chosu = await prisma.heritage.create({
    data: {
      name: '전의 초수 (왕의 물)',
      era: '조선시대 (세종)',
      dong: '전의면',
      latitude: 36.6812,
      longitude: 127.1998,
      description: '조선 세종대왕의 안질(눈병)을 치료하기 위해 한양까지 갓 길어 올린 약수가 나오던 역사의 현장입니다.',
      thinkingPoint: '세종대왕의 눈병을 고친 전의 초수의 효험과 애민정신을 느껴보세요.',
      source: 'registered',
      status: 'approved',
      likeCount: 38,
      naverMapUrl: 'https://map.naver.com/v5/search/전의초수',
      images: {
        create: [
          {
            imageUrl: 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=800&q=80',
            sortOrder: 0,
          },
        ],
      },
    },
  });

  const limnansu = await prisma.heritage.create({
    data: {
      name: '임난수 장군 숭모각 및 은행나무',
      era: '고려/조선 초',
      dong: '세종동',
      latitude: 36.4950,
      longitude: 127.2710,
      description: '고려말 절신 임난수 장군이 고려가 망하자 벼슬을 버리고 절개를 지키며 심은 600년 넘는 천연기념물 은행나무입니다.',
      thinkingPoint: '조선 창업의 거친 바람 속에서도 지켜낸 한 선비의 곧은 절개와 충절을 떠올려봅시다.',
      source: 'registered',
      status: 'approved',
      likeCount: 29,
      naverMapUrl: 'https://map.naver.com/v5/search/세종은행나무',
      images: {
        create: [
          {
            imageUrl: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80',
            sortOrder: 0,
          },
        ],
      },
    },
  });

  // 3. Citizen Reported Heritage (Pending & Approved)
  const citizenReport1 = await prisma.heritage.create({
    data: {
      name: '조치원 옛 정수장 (문화정원)',
      era: '근현대',
      dong: '조치원읍',
      latitude: 36.6015,
      longitude: 127.2990,
      description: '1930년대 근대 상수도 시설을 시민 문화 예술 공간으로 재탄생시킨 세종시 유휴공간 재생의 대표사례입니다.',
      thinkingPoint: '버려진 산업유산이 시민들의 숨쉬는 문화공간으로 탈바꿈하는 보존의 가치',
      source: 'citizen',
      status: 'approved',
      likeCount: 15,
      reportedById: citizenUser.id,
      reportReason: '조치원근대문화유산 보존과 휴식이 공존하는 최고의 시민 추천 장소입니다.',
      images: {
        create: [
          {
            imageUrl: 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80',
            sortOrder: 0,
          },
        ],
      },
    },
  });

  const pendingReport = await prisma.heritage.create({
    data: {
      name: '연기향교 대성전 및 동서재',
      era: '조선시대 (태종)',
      dong: '연기면',
      latitude: 36.5255,
      longitude: 127.2512,
      description: '조선 시대 지방 교육기관으로 학문과 례를 닦던 유서 깊은 향교입니다.',
      thinkingPoint: '지방 인재 양성과 선현 배향의 장소',
      source: 'citizen',
      status: 'pending',
      reportedById: citizenUser.id,
      reportReason: '세종시의 유교 문화유산으로서 역사적 보존 가치가 뛰어납니다.',
    },
  });

  console.log(`🏛️ Heritages seeded: Total 5 entries created.`);

  // 4. Sample Course
  const course1 = await prisma.course.create({
    data: {
      userId: citizenUser.id,
      title: '세종 역사와 왕의 물을 찾아서 (전의~비암사 코스)',
      transportMode: '자차/대중교통 추천',
      totalDurationMin: 150,
      isPublic: true,
      courseItems: {
        create: [
          { heritageId: biamsa.id, sortOrder: 1 },
          { heritageId: chosu.id, sortOrder: 2 },
          { heritageId: citizenReport1.id, sortOrder: 3 },
        ],
      },
    },
  });

  console.log(`🗺️ Public Course seeded: ${course1.title}`);

  // 5. Sample Review
  await prisma.review.create({
    data: {
      userId: citizenUser.id,
      courseId: course1.id,
      heritageId: biamsa.id,
      rating: 5,
      companionType: '가족',
      content: '비암사의 호젓한 조용함과 고요한 산사 분위기가 마음을 힐링해 줍니다. 아이들과 가기 정말 좋아요!',
      isRecommended: true,
      isPublic: true,
      parkingAvailable: true,
      parkingNote: '주차장 진입 진입로 폭이 약간 좁습니다.',
      restroomAvailable: true,
      restroomNote: '화장실은 청결하나 주말엔 약간 붐빕니다.',
    },
  });

  console.log('✅ Seeding finished successfully!');
}

main()
  .catch((e) => {
    console.error('❌ Seeding error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
