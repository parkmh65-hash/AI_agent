// App.jsx - ver_02 Supervisor Control Dashboard React Application

import React, { useState, useEffect } from 'react';
import {
  fetchInitialAppData,
  updateRecommendationStatus,
  getDatabaseStats,
  getBackendHealthStatus
} from './api';

export default function App() {
  const [citizenSubmissions, setCitizenSubmissions] = useState([]);
  const [stats, setStats] = useState({ official_count: 0, citizen_pending: 0, citizen_approved: 0 });
  const [backendHealth, setBackendHealth] = useState({ status: 'unknown', supabase_configured: false, llm_configured: false });
  const [pingLatency, setPingLatency] = useState('0ms');
  const [toastMessage, setToastMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Initialize and load dashboard details
  useEffect(() => {
    loadDashboardData();
  }, []);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 3000);
  };

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 1. Fetch tables data
      const data = await fetchInitialAppData();
      setCitizenSubmissions(data.citizen || []);

      // 2. Fetch rows counts stats
      const countStats = await getDatabaseStats();
      setStats(countStats);

      // 3. Ping backend health latency
      const start = Date.now();
      const health = await getBackendHealthStatus();
      setPingLatency(`${Date.now() - start}ms`);
      setBackendHealth(health);
    } catch (err) {
      showToast('❌ 원격 대시보드 상태를 동기화하는 중 에러가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleVetting = async (id, status) => {
    try {
      showToast(`📁 제보 심사 상태 변경 중 (${status})...`);
      const res = await updateRecommendationStatus(id, status);
      if (res.status === 'success') {
        showToast(`✅ 성공적으로 ${status} 처리 완료되었습니다.`);
        // Reload list and counts stats
        loadDashboardData();
      } else {
        showToast(`❌ 상태 업데이트 실패: ${res.message}`);
      }
    } catch (err) {
      showToast('❌ 심사 요청 처리 중 네트워크 오류가 발생했습니다.');
    }
  };

  return (
    <div style={{ padding: '30px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Toast banner popup */}
      {toastMessage && (
        <div style={{ position: 'fixed', top: '20px', right: '20px', zIndex: 9999, background: '#1e293b', border: '1px solid #3b82f6', color: '#60a5fa', padding: '12px 24px', borderRadius: '8px', fontSize: '0.85rem', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
          {toastMessage}
        </div>
      )}

      {/* Header title */}
      <header style={{ marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: '0 0 5px 0', fontSize: '1.75rem', fontWeight: 900, background: 'linear-gradient(135deg, #60a5fa, #34d399)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            전국 스마트 문화유산 감독관 시스템 ver_02
          </h1>
          <p style={{ margin: 0, fontSize: '0.9rem', color: '#9ca3af' }}>통합 플랫폼 데이터 연동 감시 및 시민 제보 심사 원격 컨트롤 센터</p>
        </div>
        <button onClick={loadDashboardData} className="action-btn" style={{ background: '#3b82f6', color: '#fff' }}>
          {loading ? '동기화 중...' : '🔄 실시간 동기화'}
        </button>
      </header>

      {/* Stats indicators grid */}
      <section className="dashboard-grid">
        <div className="stats-card">
          <span style={{ fontSize: '0.78rem', color: '#9ca3af', display: 'block', marginBottom: '6px', textTransform: 'uppercase' }}>공식 수록 문화유산</span>
          <strong style={{ fontSize: '2rem', color: '#60a5fa' }}>{stats.official_count}개</strong>
        </div>

        <div className="stats-card">
          <span style={{ fontSize: '0.78rem', color: '#9ca3af', display: 'block', marginBottom: '6px', textTransform: 'uppercase' }}>심사 대기 시민제보</span>
          <strong style={{ fontSize: '2rem', color: '#f59e0b' }}>{stats.citizen_pending}건</strong>
        </div>

        <div className="stats-card">
          <span style={{ fontSize: '0.78rem', color: '#9ca3af', display: 'block', marginBottom: '6px', textTransform: 'uppercase' }}>최종 승인 시민제보</span>
          <strong style={{ fontSize: '2rem', color: '#10b981' }}>{stats.citizen_approved}건</strong>
        </div>

        <div className="stats-card">
          <span style={{ fontSize: '0.78rem', color: '#9ca3af', display: 'block', marginBottom: '6px', textTransform: 'uppercase' }}>API 백엔드 헬스 지표</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: backendHealth.status === 'healthy' ? '#10b981' : '#ef4444', display: 'inline-block' }}></span>
            <strong style={{ fontSize: '1.1rem', color: '#fff' }}>
              {backendHealth.status === 'healthy' ? 'CONNECTED' : 'OFFLINE'}
            </strong>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>({pingLatency})</span>
          </div>
        </div>
      </section>

      {/* Main content table area */}
      <section className="stats-card" style={{ padding: '0px', overflow: 'hidden' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>🌱 접수된 시민 제보 유산 심사 대장</h3>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(255,255,255,0.02)', color: '#9ca3af' }}>
                <th style={{ padding: '14px 20px' }}>제보 유산명</th>
                <th style={{ padding: '14px 20px' }}>제보 위치 / 주소</th>
                <th style={{ padding: '14px 20px' }}>제보 사유</th>
                <th style={{ padding: '14px 20px' }}>제보 위/경도</th>
                <th style={{ padding: '14px 20px' }}>진행 상태</th>
                <th style={{ padding: '14px 20px', textAlign: 'center' }}>승인 및 반려 심사</th>
              </tr>
            </thead>
            <tbody>
              {citizenSubmissions.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px 0', textAlign: 'center', color: '#9ca3af' }}>
                    접수된 제보 내역이 존재하지 않습니다.
                  </td>
                </tr>
              ) : (
                citizenSubmissions.map((row) => (
                  <tr key={row.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)', transition: 'background 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'} onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '14px 20px', fontWeight: 'bold', color: '#fff' }}>{row.name}</td>
                    <td style={{ padding: '14px 20px', color: '#cbd5e1' }}>{row.address}</td>
                    <td style={{ padding: '14px 20px', color: '#cbd5e1', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={row.description}>
                      {row.description || '내용 없음'}
                    </td>
                    <td style={{ padding: '14px 20px', color: '#9ca3af' }}>
                      {parseFloat(row.latitude || row.lat || 0).toFixed(4)}, {parseFloat(row.longitude || row.lng || 0).toFixed(4)}
                    </td>
                    <td style={{ padding: '14px 20px' }}>
                      <span className={`badge ${row.status === '승인' ? 'badge-approved' : row.status === '반려' ? 'badge-rejected' : 'badge-pending'}`}>
                        {row.status || '대기'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 20px', display: 'flex', gap: '8px', justifyContent: 'center' }}>
                      {row.status === '대기' ? (
                        <>
                          <button onClick={() => handleVetting(row.id, '승인')} className="action-btn" style={{ background: '#10b981', color: '#fff' }}>
                            승인
                          </button>
                          <button onClick={() => handleVetting(row.id, '반려')} className="action-btn" style={{ background: '#ef4444', color: '#fff' }}>
                            반려
                          </button>
                        </>
                      ) : (
                        <span style={{ fontSize: '0.78rem', color: '#9ca3af' }}>심사 종결</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
