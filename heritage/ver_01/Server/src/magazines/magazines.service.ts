import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { EmailService } from '../email/email.service';

@Injectable()
export class MagazinesService {
  private readonly logger = new Logger(MagazinesService.name);

  constructor(
    private prisma: PrismaService,
    private emailService: EmailService,
  ) {}

  async generateMagazine(courseId: string) {
    const course = await this.prisma.course.findUnique({
      where: { id: courseId },
      include: {
        courseItems: {
          orderBy: { sortOrder: 'asc' },
          include: { heritage: { include: { images: true } } },
        },
      },
    });

    if (!course) {
      throw new NotFoundException('해당 코스를 찾을 수 없습니다.');
    }

    const items = course.courseItems.map((ci) => ci.heritage);
    const itemNames = items.map((h) => h.name).join(', ');

    // Claude API Call or High Quality Template Generator
    let aiArticleText = '';
    const apiKey = process.env.CLAUDE_API_KEY || process.env.ANTHROPIC_API_KEY;

    if (apiKey) {
      try {
        const response = await fetch('https://api.anthropic.com/v1/messages', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
          },
          body: JSON.stringify({
            model: 'claude-3-5-sonnet-20241022',
            max_tokens: 1500,
            messages: [
              {
                role: 'user',
                content: `세종시 문화유산 코스 "${course.title}" (경로: ${itemNames})에 관한 감성적이고 깊이 있는 웹 여행 잡지 기사를 작성해줘. 각 문화유산별 백그라운드 스토리와 "생각할 거리"를 다루어줘.`,
              },
            ],
          }),
        });
        const data = await response.json();
        if (data.content && data.content[0]) {
          aiArticleText = data.content[0].text;
        }
      } catch (err) {
        this.logger.warn(`Claude API call failed, falling back to local generator: ${err.message}`);
      }
    }

    if (!aiArticleText) {
      aiArticleText = `
        <h2 style="color:#1d4ed8;">역사 탐방과 자연이 어우러진 세종 문화유산 기행</h2>
        <p style="font-size:15px; line-height:1.7; color:#374151;">
          세종특별자치시는 첨단 스마트도시의 미래적 경관 속에서도 수백 년 이상의 서사와 민족의 호국·선비 정신이 살아 숨쉬는 역사적 장소입니다.
          본 코스 "<strong>${course.title || '세종 문화유산 코스'}</strong>"는 ${itemNames} (총 소요시간 약 ${course.totalDurationMin || 120}분)을 순회하며,
          시민과 방문객 모두에게 특별한 사유의 시간을 제공합니다.
        </p>
        <div style="margin:20px 0; padding:16px; background-color:#eff6ff; border-left:4px solid #3b82f6; border-radius:6px;">
          <h3 style="margin-top:0; color:#1e40af;">💡 코스 핵심 요약</h3>
          <ul style="margin-bottom:0; color:#1e3a8a;">
            <li>추천 교통 수단: <strong>${course.transportMode || '도보/자차'}</strong></li>
            <li>총 예상 소요 시간: <strong>약 ${course.totalDurationMin || 120}분</strong></li>
            <li>방문 대상 문화유산: <strong>${items.length}곳</strong></li>
          </ul>
        </div>
      `;
    }

    // Generate Complete HTML Magazine layout
    const contentHtml = `
      <!DOCTYPE html>
      <html lang="ko">
      <head>
        <meta charset="UTF-8">
        <title>세종시 AI 문화유산 여행잡지 - ${course.title}</title>
        <style>
          body { font-family: 'Pretendard', 'Noto Sans KR', sans-serif; margin:0; padding:20px; background:#f8fafc; color:#1e293b; }
          .container { max-width: 720px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
          .header { text-align: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 24px; }
          .title { font-size: 26px; color: #0f172a; margin: 8px 0; font-weight: 700; }
          .subtitle { color: #64748b; font-size: 14px; }
          .item-card { border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }
          .item-img { width: 100%; height: 240px; object-fit: cover; background: #cbd5e1; }
          .item-body { padding: 16px; }
          .thinking-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; border-radius: 4px; margin-top: 10px; font-size: 13px; color: #92400e; }
          .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 16px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <span style="background:#dbeafe; color:#1d4ed8; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold;">세종 특별시 AI 여행잡지</span>
            <h1 class="title">${course.title}</h1>
            <div class="subtitle">AI가 추천하는 커스텀 동선 기행문 • 작성일: ${new Date().toLocaleDateString('ko-KR')}</div>
          </div>

          <div class="article-content">
            ${aiArticleText}
          </div>

          <h3 style="margin-top:32px; color:#0f172a;">📍 코스 내 주요 문화유산 가이드</h3>
          ${items
            .map(
              (h, idx) => `
            <div class="item-card">
              ${
                h.images && h.images.length > 0
                  ? `<img class="item-img" src="${h.images[0].imageUrl}" alt="${h.name}">`
                  : ''
              }
              <div class="item-body">
                <h4 style="margin:0 0 8px 0; color:#1e293b; font-size:18px;">${idx + 1}. ${h.name} (${h.era || '시대 미상'}, ${h.dong || '세종시'})</h4>
                <p style="font-size:14px; color:#475569; margin:0 0 10px 0;">${h.description || '세종시 대표 문화유산'}</p>
                ${
                  h.thinkingPoint
                    ? `<div class="thinking-box">💭 <strong>생각할 거리:</strong> ${h.thinkingPoint}</div>`
                    : ''
                }
              </div>
            </div>
          `,
            )
            .join('')}

          <div class="footer">
            본 매거진은 세종특별자치시 AI 문화유산 스마트 플랫폼에서 생성되었습니다.
          </div>
        </div>
      </body>
      </html>
    `;

    const magazine = await this.prisma.travelMagazine.create({
      data: {
        courseId,
        contentHtml,
        pdfUrl: `https://storage.sejong.go.kr/magazines/${courseId}.pdf`,
      },
    });

    return magazine;
  }

  async sendMagazine(courseId: string, email: string) {
    let magazine = await this.prisma.travelMagazine.findFirst({
      where: { courseId },
      orderBy: { createdAt: 'desc' },
    });

    if (!magazine) {
      magazine = await this.generateMagazine(courseId);
    }

    const course = await this.prisma.course.findUnique({ where: { id: courseId } });
    const title = course?.title || '세종시 문화유산 여행 코스';

    await this.emailService.sendMagazineEmail(email, title, magazine.contentHtml, magazine.pdfUrl);

    const updated = await this.prisma.travelMagazine.update({
      where: { id: magazine.id },
      data: {
        sentToEmail: email,
        sentAt: new Date(),
      },
    });

    return {
      message: `${email} 주소로 AI 여행잡지가 성공적으로 발송되었습니다.`,
      magazine: updated,
    };
  }
}
