import { Module } from '@nestjs/common';
import { HeritagesService } from './heritages.service';
import { HeritagesController } from './heritages.controller';

@Module({
  controllers: [HeritagesController],
  providers: [HeritagesService],
  exports: [HeritagesService],
})
export class HeritagesModule {}
