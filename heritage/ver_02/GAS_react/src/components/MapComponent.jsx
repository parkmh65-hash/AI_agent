// MapComponent.jsx - ver_02 Leaflet Map Visualization Component

import React, { useEffect, useRef } from 'react';

export default function MapComponent({ courseList = [] }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const polylineRef = useRef(null);

  useEffect(() => {
    // Leaflet global check (loaded via cdn in index.html)
    if (typeof L === 'undefined' || !mapContainerRef.current) return;

    // Initialize Map if not already created
    if (!mapInstanceRef.current) {
      try {
        const map = L.map(mapContainerRef.current, {
          zoomControl: true,
          scrollWheelZoom: true
        }).setView([36.55, 127.25], 11);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 18,
          attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        mapInstanceRef.current = map;
      } catch (err) {
        console.error("Leaflet initialization failed:", err);
        return;
      }
    }

    const map = mapInstanceRef.current;

    // Clear existing markers & lines
    markersRef.current.forEach(marker => map.removeLayer(marker));
    markersRef.current = [];

    if (polylineRef.current) {
      map.removeLayer(polylineRef.current);
      polylineRef.current = null;
    }

    // Build markers & line paths
    const latlngs = [];

    courseList.forEach((item, index) => {
      const lat = parseFloat(item.latitude || item.lat) || 36.48;
      const lng = parseFloat(item.longitude || item.lng) || 127.28;
      latlngs.push([lat, lng]);

      // Custom marker icon showing sequence index number
      const indexIcon = L.divIcon({
        className: 'custom-sequence-marker',
        html: `
          <div style="
            background: linear-gradient(135deg, #00f5d4, #7209b7);
            color: #ffffff;
            font-weight: 900;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 0 10px rgba(0, 245, 212, 0.8);
            font-size: 0.85rem;
          ">
            ${index + 1}
          </div>
        `,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });

      const popupHtml = `
        <div style="font-family: sans-serif; font-size: 0.85rem; color: #0f172a; padding: 4px; min-width: 180px;">
          <strong style="color: #7209b7; font-size: 0.95rem; display: block; margin-bottom: 4px;">
            ${index + 1}. ${item.name}
          </strong>
          <span style="color: #64748b; font-size: 0.8rem; display: block; margin-bottom: 4px;">
            📍 주소: ${item.address || '세종시'}
          </span>
          <span style="display: inline-block; padding: 2px 6px; background: #e0f2fe; color: #0369a1; border-radius: 4px; font-size: 0.72rem; font-weight: 700;">
            🏛️ ${item.category || '조선시대'}
          </span>
        </div>
      `;

      const marker = L.marker([lat, lng], { icon: indexIcon }).addTo(map);
      marker.bindPopup(popupHtml);
      
      if (index === 0) {
        marker.openPopup();
      }
      
      markersRef.current.push(marker);
    });

    // Draw connecting line if multiple heritages
    if (latlngs.length > 1) {
      const line = L.polyline(latlngs, {
        color: '#00f5d4',
        weight: 4,
        opacity: 0.85,
        dashArray: '5, 10'
      }).addTo(map);

      polylineRef.current = line;
      map.fitBounds(line.getBounds(), { padding: [30, 30] });
    } else if (latlngs.length === 1) {
      map.setView(latlngs[0], 13);
    }

    // Force redraw layout
    setTimeout(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    }, 200);

  }, [courseList]);

  // Clean map container on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.remove();
        } catch (e) {
          console.warn("Map teardown error:", e);
        }
        mapInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <div 
      ref={mapContainerRef} 
      style={{
        width: '100%',
        height: '100%',
        background: '#090d16',
        borderRadius: '16px',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        zIndex: 1
      }}
    />
  );
}
