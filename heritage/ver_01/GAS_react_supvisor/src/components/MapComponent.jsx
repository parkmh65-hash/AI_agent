import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

export default function MapComponent({ courseList = [] }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Clean up previous map instance
    if (mapInstanceRef.current) {
      try {
        mapInstanceRef.current.remove();
      } catch (e) {
        console.warn('Map remove error:', e);
      }
      mapInstanceRef.current = null;
    }

    try {
      const defaultLat = 36.55;
      const defaultLng = 127.25;

      const map = L.map(mapContainerRef.current, { zoomControl: true })
        .setView([defaultLat, defaultLng], 11);
      
      mapInstanceRef.current = map;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      // Distinct coords list for Sejong
      const coordList = [
        [36.6345, 127.2341], // 1. 비암사
        [36.5982, 127.2985], // 2. 연기아문
        [36.6841, 127.2023], // 3. 전의초수
        [36.5050, 127.2512], // 4. 초려이유태묘소
        [36.5218, 127.3482]  // 5. 세종합강정
      ];

      const defaultAddresses = [
        '세종특별자치시 전의면 다방리 137',
        '세종특별자치시 연기면 연기리 32',
        '세종특별자치시 전의면 관정리 149',
        '세종특별자치시 어진동 143 (초려역사공원)',
        '세종특별자치시 연동면 태산로 749'
      ];

      const latLngs = [];

      courseList.forEach((item, idx) => {
        const fallbackCoord = coordList[idx % coordList.length];
        const fallbackAddr = defaultAddresses[idx % defaultAddresses.length];

        const lat = parseFloat(item.latitude || item.lat) || fallbackCoord[0];
        const lng = parseFloat(item.longitude || item.lng) || fallbackCoord[1];
        const displayAddr = item.address || fallbackAddr;

        latLngs.push([lat, lng]);

        const markerHtml = `
          <div style="
            background: linear-gradient(135deg, #00f5d4, #7209b7);
            color: #fff;
            font-weight: 900;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2.5px solid #fff;
            box-shadow: 0 0 16px rgba(0,245,212,0.9);
            font-size: 0.92rem;
          ">
            ${idx + 1}
          </div>
        `;

        const customIcon = L.divIcon({
          html: markerHtml,
          className: 'custom-course-marker',
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        });

        const popupContent = `
          <div style="font-family: sans-serif; font-size: 0.88rem; color: #0f172a; padding: 6px; min-width: 200px;">
            <strong style="color: #7209b7; font-size: 1rem; display:block; margin-bottom:4px;">${idx + 1}. ${item.name || '문화유산'}</strong>
            <span style="color: #334155; font-size: 0.82rem; display:block; margin-bottom:4px; font-weight:600;">📍 주소: ${displayAddr}</span>
            <span style="display:inline-block; padding:3px 8px; background:#00f5d4; color:#0f172a; font-weight:800; border-radius:6px; font-size:0.75rem;">🏛️ ${item.era || '조선시대'}</span>
          </div>
        `;

        const marker = L.marker([lat, lng], { icon: customIcon }).addTo(map);
        marker.bindPopup(popupContent);
        if (idx === 0) marker.openPopup();
      });

      if (latLngs.length > 1) {
        const polyline = L.polyline(latLngs, {
          color: '#00f5d4',
          weight: 4,
          opacity: 0.9,
          dashArray: '8, 8'
        }).addTo(map);
        map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
      } else if (latLngs.length === 1) {
        map.setView(latLngs[0], 13);
      }

      // Fix render size
      setTimeout(() => {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.invalidateSize();
        }
      }, 200);

      setUseFallback(false);
    } catch (err) {
      console.warn('Leaflet error, showing fallback vector visualizer:', err);
      setUseFallback(true);
    }

    return () => {
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.remove();
        } catch (e) {
          console.warn('Cleanup map error:', e);
        }
        mapInstanceRef.current = null;
      }
    };
  }, [courseList]);

  if (useFallback) {
    return <VectorFallbackMap courseList={courseList} />;
  }

  return (
    <div
      ref={mapContainerRef}
      style={{
        width: '100%',
        height: '100%',
        background: '#0f172a',
        borderRadius: '14px',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        zIndex: 1
      }}
    />
  );
}

// Local SVG Fallback Renderer (similar to renderSVGVectorRouteMap)
function VectorFallbackMap({ courseList = [] }) {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'radial-gradient(circle, #1c2541 0%, #0b132b 100%)',
        borderRadius: '14px',
        border: '1px solid rgba(255,255,255,0.12)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}
    >
      <h4 style={{ color: '#00f5d4', margin: '0 0 16px 0', fontSize: '1rem', fontWeight: 800 }}>
        🗺️ 세종시 코스 시각화 노드 맵 (시뮬레이터)
      </h4>
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap', justifyContent: 'center' }}>
        {courseList.length === 0 ? (
          <div style={{ color: '#a0aec0', fontSize: '0.9rem' }}>
            등록된 코스가 없습니다. 문화유산을 추가해 주세요.
          </div>
        ) : (
          courseList.map((item, idx) => (
            <React.Fragment key={idx}>
              <div
                style={{
                  background: 'rgba(28, 37, 65, 0.85)',
                  border: '1px solid #00f5d4',
                  borderRadius: '12px',
                  padding: '12px 18px',
                  textAlign: 'center',
                  boxShadow: '0 4px 15px rgba(0, 245, 212, 0.15)',
                  minWidth: '100px'
                }}
              >
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: '#00f5d4',
                    color: '#0b132b',
                    fontWeight: 800,
                    margin: '0 auto 6px auto',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.8rem'
                  }}
                >
                  {idx + 1}
                </div>
                <div style={{ color: '#fff', fontSize: '0.85rem', fontWeight: 700 }}>
                  {item.name}
                </div>
                <div style={{ color: '#a0aec0', fontSize: '0.75rem' }}>
                  {item.dong || '세종시'}
                </div>
              </div>
              {idx < courseList.length - 1 && (
                <div style={{ color: '#00f5d4', fontSize: '1.5rem', fontWeight: 900 }}>
                  ➔
                </div>
              )}
            </React.Fragment>
          ))
        )}
      </div>
    </div>
  );
}
