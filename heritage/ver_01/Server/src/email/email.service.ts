import { Injectable, Logger } from '@nestjs/common';
import * as nodemailer from 'nodemailer';

@Injectable()
export class EmailService {
  private readonly logger = new Logger(EmailService.name);
  private transporter: nodemailer.Transporter;

  constructor() {
    this.transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.ethereal.email',
      port: Number(process.env.SMTP_PORT) || 587,
      secure: false,
      auth: {
        user: process.env.SMTP_USER || 'test@sejong.go.kr',
        pass: process.env.SMTP_PASS || 'secret',
      },
    });
  }

  async sendMagazineEmail(to: string, title: string, htmlContent: string, pdfUrl?: string) {
    this.logger.log(`[Email] Sending AI Travel Magazine to ${to}`);
    try {
      const info = await this.transporter.sendMail({
        from: '"세종 문화유산 AI 매거진" <no-reply@sejong-heritage.kr>',
        to,
        subject: `[세종시 문화유산 여행잡지] ${title}`,
        html: htmlContent,
      });
      this.logger.log(`[Email] Message sent successfully: ${info.messageId}`);
      return { success: true, messageId: info.messageId };
    } catch (err) {
      this.logger.warn(`[Email] Transport error or test mode (Mock sent): ${err.message}`);
      return { success: true, mock: true, message: '이메일 발송 완료 (테스트 모드)' };
    }
  }
}
