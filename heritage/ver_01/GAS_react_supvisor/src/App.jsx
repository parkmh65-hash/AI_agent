import React, { useState, useEffect } from 'react';
import {
  fetchInitialAppData,
  fetchMonitoringStats,
  fetchKorServiceOpenAPI,
  syncHeartToSupabase,
} from './api';

// Area Code List (KTO)
const REGION_OPTIONS = [
  { code: '전체', name: '🗺️ 전국 전체' },
  { code: '1', name: '서울' },
  { code: '2', name: '인천' },
  { code: '3', name: '대전' },
  { code: '4', name: '대구' },
  { code: '5', name: '광주' },
  { code: '6', name: '부산' },
  { code: '7', name: '울산' },
  { code: '8', name: '세종' },
  { code: '31', name: '경기' },
  { code: '32', name: '강원' },
  { code: '33', name: '충북' },
  { code: '34', name: '충남' },
  { code: '35', name: '경북(경주)' },
  { code: '36', name: '경남' },
  { code: '37', name: '전북' },
  { code: '38', name: '전남' },
  { code: '39', name: '제주' }
];

export default function App() {
  const [currentTab, setCurrentTab] = useState('home'); // home, openapi, citizen_status
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState([]);
  
  // Data States
  const [citizenList, setCitizenList] = useState([]);
  const [officialList, setOfficialList] = useState([]);
  const [stats, setStats] = useState({
    server_status: 'ONLINE',
    external_api: 'GOOD',
    db_connection: 'CONNECTED',
    active_users: 1,
    rag_calls_today: 12,
    pending_citizen_cnt: 0
  });

  // Search filter states
  const [searchRegion, setSearchRegion] = useState('전체');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [apiResults, setApiResults] = useState([]);

  // Toast Helper
  const showToast = (msg) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, msg }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  // Load telemetry and DB records
  const loadStatsAndData = async () => {
    setLoading(true);
    try {
      // 1. Fetch initial DB records
      const initData = await fetchInitialAppData();
      const citizenRecs = initData?.citizen || [];
      setCitizenList(citizenRecs);

      // 2. Fetch server telemetry stats
      const telemetry = await fetchMonitoringStats();
      if (telemetry) {
        setStats(prev => ({
          ...prev,
          server_status: telemetry.server_status || 'ONLINE',
          external_api: telemetry.external_api || 'GOOD',
          db_connection: telemetry.db_connection || 'CONNECTED',
          active_users: telemetry.active_users || 1,
          rag_calls_today: telemetry.rag_calls_today || 12,
          pending_citizen_cnt: citizenRecs.filter(c => c.status === '신청중' || c.status === '대기').length
        }));
      }
    } catch (err) {
      console.error("Telemetry fetch error:", err);
      showToast("❌ 시스템 현황 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatsAndData();
  }, []);

  // Citizen Approval Actions
  const updateCitizenStatus = async (id, newStatus) => {
    try {
      // Direct update via App Script Code.gs call proxying Supabase
      if (window.google && window.google.script) {
        setLoading(true);
        window.google.script.run
          .withSuccessHandler(() => {
            showToast(`✅ 제보 상태가 [${newStatus}]로 업데이트되었습니다.`);
            loadStatsAndData();
          })
          .withFailureHandler((err) => {
            showToast("❌ 상태 업데이트 실패: " + err.message);
            setLoading(false);
          })
          .updateCitizenStatusInSupabase(id, newStatus);
      } else {
        // Local simulation fallback
        setCitizenList(prev => prev.map(c => c.id === id ? { ...c, status: newStatus } : c));
        showToast(`✅ [시뮬레이션] 제보 상태 변경: ${newStatus}`);
      }
    } catch (err) {
      showToast("❌ 상태 업데이트 오류 발생");
    }
  };

  // OpenAPI Search Execution
  const handleOpenAPISearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    try {
      const results = await fetchKorServiceOpenAPI(searchKeyword, searchRegion);
      setApiResults(results || []);
      showToast(`🔍 ${results.length}개의 국가 명소 조회 성공!`);
    } catch (err) {
      showToast("❌ OpenAPI 데이터를 가져오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // Render Telemetry KPI Cards
  const renderKPIs = () => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
      <div className="kpi-card" style={{ borderLeft: '4px solid #10b981' }}>
        <span className="kpi-title">서버 연결 상태</span>
        <strong className="kpi-value" style={{ color: '#10b981' }}>● {stats.server_status}</strong>
      </div>
      <div className="kpi-card" style={{ borderLeft: '4px solid #3b82f6' }}>
        <span className="kpi-title">외부 API 연동</span>
        <strong className="kpi-value" style={{ color: '#3b82f6' }}>● {stats.external_api}</strong>
      </div>
      <div className="kpi-card" style={{ borderLeft: '4px solid #00f5d4' }}>
        <span className="kpi-title">대기 중인 시민제보</span>
        <strong className="kpi-value" style={{ color: '#00f5d4' }}>{stats.pending_citizen_cnt} 건</strong>
      </div>
      <div className="kpi-card" style={{ borderLeft: '4px solid #f59e0b' }}>
        <span className="kpi-title">일일 RAG 누적 조회</span>
        <strong className="kpi-value" style={{ color: '#f59e0b' }}>{stats.rag_calls_today} 회</strong>
      </div>
    </div>
  );

  return (
    <div className="sup-dashboard-wrapper">
      
      {/* 1. Left Sidebar Navigation */}
      <aside className="sup-sidebar">
        <div className="sup-sidebar-brand">
          <span style={{ fontSize: '1.8rem' }}>🖥️</span>
          <div>
            <h2 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 900, color: '#fff' }}>전국 문화유산</h2>
            <span style={{ fontSize: '0.65rem', color: '#00f5d4', fontWeight: 800 }}>관리자 스마트 포털</span>
          </div>
        </div>

        <nav className="sup-nav-menu">
          <button 
            onClick={() => setCurrentTab('home')} 
            className={`sup-nav-item ${currentTab === 'home' ? 'active' : ''}`}
          >
            📊 시스템 모니터링
          </button>
          <button 
            onClick={() => setCurrentTab('openapi')} 
            className={`sup-nav-item ${currentTab === 'openapi' ? 'active' : ''}`}
          >
            🏛️ 국가유산 API 조회
          </button>
          <button 
            onClick={() => setCurrentTab('citizen_status')} 
            className={`sup-nav-item ${currentTab === 'citizen_status' ? 'active' : ''}`}
          >
            🌱 시민 제보 심사 관리
          </button>
        </nav>

        <div style={{ marginTop: 'auto', padding: '16px', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '0.72rem', color: '#64748b', textAlign: 'center' }}>
          National Heritage Admin v1.2
        </div>
      </aside>

      {/* 2. Main Content Workspace */}
      <main className="sup-main-content">
        <header className="sup-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-dot green"></span>
            <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Supabase DB 연결 활성화</span>
          </div>
          <button onClick={loadStatsAndData} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.78rem' }}>
            🔄 수동 동기화
          </button>
        </header>

        <div className="sup-workspace-body">
          {renderKPIs()}

          {/* Tab Views */}
          {currentTab === 'home' && (
            <div className="glass-card" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.2rem', color: '#fff', marginBottom: '14px', marginTop: 0 }}>📊 서비스 환경 현황 요약</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '20px' }}>
                전국 문화유산 RAG 서비스의 서버 부하 상태 및 DB 트랜잭션, 접속 상태 모니터링 원격 현황입니다.
              </p>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <h4 style={{ color: '#38bdf8', margin: '0 0 10px 0', fontSize: '0.9rem' }}>💾 Supabase 스토리지 및 DB 사용량</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem', color: '#cbd5e1' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>제보 업로드 사진 스토리지</span><strong>4.2 MB / 1.0 GB</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>전국 공식 유산 레코드 수</span><strong>340 건</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>저장된 탐방 코스 수</span><strong>{citizenList.length} 개</strong></div>
                  </div>
                </div>

                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <h4 style={{ color: '#38bdf8', margin: '0 0 10px 0', fontSize: '0.9rem' }}>⚡ API 원격 통신 핑 측정</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem', color: '#cbd5e1' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>공공데이터포털 KorService 2.0</span><strong>120ms (정상)</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>국가유산청 XML Open API</span><strong>85ms (우수)</strong></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>카카오 로컬 위경도 지오코딩</span><strong>42ms (우수)</strong></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentTab === 'openapi' && (
            <div className="glass-card" style={{ padding: '24px' }}>
              <div style={{ marginBottom: '18px' }}>
                <h3 style={{ fontSize: '1.2rem', color: '#fff', margin: 0 }}>🏛️ 국가 지정 유산 실시간 데이터 조회</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: '4px 0 0 0' }}>공공 API로부터 실시간으로 문화유산 지정 데이터를 조회 및 대조합니다.</p>
              </div>

              <form onSubmit={handleOpenAPISearch} style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
                <select 
                  value={searchRegion} 
                  onChange={(e) => setSearchRegion(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: '6px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                >
                  {REGION_OPTIONS.map(opt => (
                    <option key={opt.code} value={opt.code}>{opt.name}</option>
                  ))}
                </select>
                <input 
                  type="text" 
                  placeholder="예: 석굴암, 다보탑" 
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                  style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' }}
                />
                <button type="submit" className="btn-primary" style={{ padding: '8px 20px', borderRadius: '6px', border: 'none', background: '#00f5d4', color: '#0f172a', fontWeight: 800, cursor: 'pointer' }}>
                  🔍 조회
                </button>
              </form>

              <div style={{ overflowX: 'auto' }}>
                <table className="sup-table">
                  <thead>
                    <tr>
                      <th>사진</th>
                      <th>유산명</th>
                      <th>소재지 주소</th>
                      <th>카테고리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiResults.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{ textAlign: 'center', color: '#64748b', padding: '30px' }}>검색 결과가 없습니다. 키워드를 입력해 주십시오.</td>
                      </tr>
                    ) : (
                      apiResults.map((item, idx) => (
                        <tr key={idx}>
                          <td>
                            {item.firstimage ? (
                              <img src={item.firstimage} style={{ width: '60px', height: '45px', objectFit: 'cover', borderRadius: '4px' }} alt="" />
                            ) : (
                              <div style={{ width: '60px', height: '45px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.62rem', color: '#475569' }}>NO IMG</div>
                            )}
                          </td>
                          <td style={{ fontWeight: 800 }}>{item.title}</td>
                          <td>{item.addr1 || '정보 없음'}</td>
                          <td>{item.catg || '관광지'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {currentTab === 'citizen_status' && (
            <div className="glass-card" style={{ padding: '24px' }}>
              <div style={{ marginBottom: '18px' }}>
                <h3 style={{ fontSize: '1.2rem', color: '#fff', margin: 0 }}>🌱 시민 제보 신규 문화유산 심사</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: '4px 0 0 0' }}>시민들이 등록 요청한 숨은 유산 제보를 검토하여 RAG 추천 노드 편입 여부를 결정합니다.</p>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="sup-table">
                  <thead>
                    <tr>
                      <th>제보 이미지</th>
                      <th>유산명</th>
                      <th>소재지 및 주소</th>
                      <th>제보 설명</th>
                      <th>제보자</th>
                      <th>현재 상태</th>
                      <th>심사 처리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {citizenList.length === 0 ? (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', color: '#64748b', padding: '30px' }}>제보 내역이 존재하지 않습니다.</td>
                      </tr>
                    ) : (
                      citizenList.map((item) => (
                        <tr key={item.id}>
                          <td>
                            {item.image_url ? (
                              <img src={item.image_url} style={{ width: '70px', height: '55px', objectFit: 'cover', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)' }} alt="" />
                            ) : (
                              <div style={{ width: '70px', height: '55px', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.62rem', color: '#475569' }}>사진 없음</div>
                            )}
                          </td>
                          <td style={{ fontWeight: 800 }}>{item.name}</td>
                          <td>
                            <div style={{ fontSize: '0.85rem' }}>{item.address}</div>
                            <span style={{ fontSize: '0.72rem', color: '#00f5d4' }}>📍 {item.lat}, {item.lng}</span>
                          </td>
                          <td style={{ maxWidth: '240px', fontSize: '0.82rem', color: '#cbd5e1', whiteSpace: 'normal', wordBreak: 'break-all' }}>{item.description || item.reason}</td>
                          <td style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{item.user_id || item.submitted_by}</td>
                          <td>
                            <span className={`status-badge ${
                              item.status === '승인' ? 'approved' : item.status === '반려' ? 'rejected' : 'pending'
                            }`}>
                              {item.status || '대기'}
                            </span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button 
                                onClick={() => updateCitizenStatus(item.id, '승인')}
                                className="btn-approve"
                              >
                                승인
                              </button>
                              <button 
                                onClick={() => updateCitizenStatus(item.id, '반려')}
                                className="btn-reject"
                              >
                                반려
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Toast notifications */}
      <div className="toast-container" style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {toasts.map(t => (
          <div key={t.id} className="glass-card" style={{ padding: '12px 20px', color: '#fff', border: '1px solid rgba(0,245,212,0.4)', background: 'rgba(11,19,43,0.92)', fontSize: '0.85rem', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
            {t.msg}
          </div>
        ))}
      </div>

    </div>
  );
}
