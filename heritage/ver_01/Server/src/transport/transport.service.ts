import { Injectable } from '@nestjs/common';

@Injectable()
export class TransportService {
  async calculateRoute(heritages: Array<{ id: string; name: string; latitude?: number; longitude?: number }>) {
    if (!heritages || heritages.length === 0) {
      return {
        transportMode: '도보',
        totalDurationMin: 0,
        totalDistanceKm: 0,
        sections: [],
      };
    }

    let totalDistanceKm = 0;
    const sections = [];

    for (let i = 0; i < heritages.length - 1; i++) {
      const from = heritages[i];
      const to = heritages[i + 1];

      let distKm = 1.5; // fallback
      if (from.latitude && from.longitude && to.latitude && to.longitude) {
        distKm = this.getDistanceKm(from.latitude, from.longitude, to.latitude, to.longitude);
      }

      // 추천 수단 계산
      let mode = '도보';
      let duration = Math.round((distKm / 4) * 60); // 4km/h
      if (distKm > 3) {
        mode = '자차/대중교통';
        duration = Math.round((distKm / 30) * 60) + 10;
      }

      totalDistanceKm += distKm;
      sections.push({
        from: from.name,
        to: to.name,
        distanceKm: Math.round(distKm * 100) / 100,
        mode,
        durationMin: duration,
      });
    }

    let overallMode = '도보';
    if (totalDistanceKm > 4) {
      overallMode = '자차/대중교통 추천';
    } else if (totalDistanceKm > 2) {
      overallMode = '도보/자전거 추천';
    }

    // 각 지점 체류시간 (지점당 약 30분 감상) + 이동시간
    const totalTravelDuration = sections.reduce((sum, s) => sum + s.durationMin, 0);
    const totalStayDuration = heritages.length * 30;
    const totalDurationMin = totalTravelDuration + totalStayDuration;

    return {
      transportMode: overallMode,
      totalDurationMin,
      totalDistanceKm: Math.round(totalDistanceKm * 100) / 100,
      sections,
    };
  }

  private getDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }
}
