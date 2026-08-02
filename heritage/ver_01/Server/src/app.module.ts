import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { HeritagesModule } from './heritages/heritages.module';
import { HomeModule } from './home/home.module';
import { CoursesModule } from './courses/courses.module';
import { TransportModule } from './transport/transport.module';
import { ReviewsModule } from './reviews/reviews.module';
import { MagazinesModule } from './magazines/magazines.module';
import { EmailModule } from './email/email.module';
import { MyModule } from './my/my.module';
import { AdminModule } from './admin/admin.module';

@Module({
  imports: [
    ScheduleModule.forRoot(),
    PrismaModule,
    AuthModule,
    UsersModule,
    HeritagesModule,
    HomeModule,
    CoursesModule,
    TransportModule,
    ReviewsModule,
    MagazinesModule,
    EmailModule,
    MyModule,
    AdminModule,
  ],
})
export class AppModule {}
