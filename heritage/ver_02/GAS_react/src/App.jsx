// App.jsx - ver_02 User Client React Application

import React, { useState, useEffect, useRef } from 'react';
import MapComponent from './components/MapComponent';
import {
  fetchInitialAppData,
  submitCitizenRecommendation,
  fetchSavedCourses,
  uploadImageToSupabaseStorage,
  executeRAGQuery,
  generateGuidebook
} from './api';

export default function App() {
  // 1. App State Declarations
  const [currentTab, setCurrentTab] = useState('home'); // 'home', 'course', 'report'
  const [officialHeritages, setOfficialHeritages] = useState([]);
  const [citizenHeritages, setCitizenHeritages] = useState([]);
  const [courseList, setCourseList] = useState([]);
  const [toastMessages, setToastMessages] = useState([]);
  
  // Navigation states
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  // RAG recommendation state
  const [ragQuery, setRagQuery] = useState('');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragCards, setRagCards] = useState([]);
  const [ragOutputText, setRagOutputText] = useState('');

  // Course planner state
  const [transport, setTransport] = useState('승용차');
  const [totalTimeText, setTotalTimeText] = useState('0분');

  // Guidebook state
  const [guidebookLoading, setGuidebookLoading] = useState(false);
  const [guidebookResult, setGuidebookResult] = useState(null);

  // Audio Speech TTS States
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  // Citizen submission form states
  const [reportName, setReportName] = useState('');
  const [reportAddress, setReportAddress] = useState('');
  const [reportLat, setReportLat] = useState('36.4800');
  const [reportLng, setReportLng] = useState('127.2800');
  const [reportReason, setReportReason] = useState('');
  const [reportPhotoBase64, setReportPhotoBase64] = useState('');
  const [reportPhotoPreview, setReportPhotoPreview] = useState('');

  const guidebookRef = useRef(null);

  // Handle mobile resizing responsive layout
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Sync journey duration time whenever course changes
  useEffect(() => {
    calculateTotalDuration();
  }, [courseList, transport]);

  // Initial Data Mount
  useEffect(() => {
    loadAppData();
  }, []);

  // Stop Speech TTS on exit
  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
    };
  }, []);

  // 2. Client Utility & Interaction Methods
  const showToast = (message) => {
    const id = Date.now() + Math.random();
    setToastMessages(prev => [...prev, { id, message }]);
    setTimeout(() => {
      setToastMessages(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  const loadAppData = async () => {
    try {
      showToast('⏳ 초기 데이터를 불러오는 중...');
      const data = await fetchInitialAppData();
      
      const officialNorm = (data.official || []).map(item => ({
        id: item.id || `h_${item.h_id || Math.random()}`,
        name: item.name,
        address: item.address || '세종시',
        category: item.category || '기타',
        latitude: parseFloat(item.latitude || item.lat) || 36.48,
        longitude: parseFloat(item.longitude || item.lng) || 127.28,
        description: item.description || '세종시의 대표 역사 문화유산입니다.',
        image_url: item.image_url || 'https://via.placeholder.com/150'
      }));

      const citizenNorm = (data.citizen || []).map(item => ({
        id: item.id || `c_${Math.random()}`,
        name: item.name,
        address: item.address || '세종시',
        category: '시민 추천',
        latitude: parseFloat(item.latitude || item.lat) || 36.48,
        longitude: parseFloat(item.longitude || item.lng) || 127.28,
        description: item.description || '시민 제보 탐방 코스',
        image_url: item.image_url || 'https://via.placeholder.com/150'
      }));

      setOfficialHeritages(officialNorm);
      setCitizenHeritages(citizenNorm);
      
      // Default recommended list
      if (officialNorm.length > 0) {
        setRagCards(officialNorm.slice(0, 3));
      }
    } catch (err) {
      showToast('❌ 초기 로딩 오류가 발생했습니다.');
    }
  };

  const calculateTotalDuration = () => {
    if (courseList.length === 0) {
      setTotalTimeText('0분');
      return;
    }
    // Simple mock heuristic routing duration index (mins)
    const factor = transport === '도보' ? 45 : transport === '대중교통' ? 25 : 12;
    const totalMins = (courseList.length * 30) + (Math.max(0, courseList.length - 1) * factor);
    
    if (totalMins >= 60) {
      const hrs = Math.floor(totalMins / 60);
      const mins = totalMins % 60;
      setTotalTimeText(`${hrs}시간 ${mins}분`);
    } else {
      setTotalTimeText(`${totalMins}분`);
    }
  };

  const addToCourse = (item) => {
    if (courseList.some(c => c.id === item.id)) {
      showToast('이미 코스에 추가되었습니다.');
    } else {
      setCourseList(prev => [...prev, item]);
      showToast(`🧭 '${item.name}' 유산이 코스에 담겼습니다.`);
    }
  };

  const addAllToCourse = (items) => {
    const newItems = items.filter(it => !courseList.some(c => c.id === it.id));
    if (newItems.length === 0) {
      showToast('모든 유산이 이미 코스에 추가되어 있습니다.');
      return;
    }
    setCourseList(prev => [...prev, ...newItems]);
    showToast(`🗺️ ${newItems.length}개의 유산을 코스에 일괄 추가했습니다.`);
  };

  const handleRAGSearch = async () => {
    if (!ragQuery.trim()) {
      showToast('추천 질문 키워드를 입력해 주세요.');
      return;
    }
    setRagLoading(true);
    try {
      const res = await executeRAGQuery(ragQuery);
      if (res.output_heritages) {
        setRagCards(res.output_heritages);
      }
      setRagOutputText(res.final_output || 'AI 추천 결과 도출이 성공적으로 완료되었습니다.');
      showToast('✅ AI 맞춤 유산 추천 완료!');
    } catch (err) {
      showToast('❌ AI 추천을 진행하는 도중 에러가 발생했습니다.');
    } finally {
      setRagLoading(false);
    }
  };

  const handleCreateGuidebook = async () => {
    if (courseList.length === 0) {
      showToast('코스 빌더에 문화유산이 최소 1개 이상 필요합니다.');
      return;
    }
    setGuidebookLoading(true);
    try {
      const names = courseList.map(c => c.name);
      const res = await generateGuidebook(names, transport);
      setGuidebookResult(res);
      showToast('✅ AI 멀티에이전트 가이드북이 생성되었습니다!');
      
      setTimeout(() => {
        guidebookRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
    } catch (err) {
      showToast('❌ 가이드북 생성 도중 오류가 발생했습니다.');
    } finally {
      setGuidebookLoading(false);
    }
  };

  // TTS Voice player controllers
  const startNarrativeTTS = () => {
    if (!guidebookResult || !guidebookResult.final_output) return;
    window.speechSynthesis.cancel();

    // Remove markdown symbols for audio reading
    const utteranceText = guidebookResult.final_output
      .replace(/###/g, '')
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/📌/g, '')
      .replace(/-/g, '');

    const utterance = new SpeechSynthesisUtterance(utteranceText);
    utterance.lang = 'ko-KR';
    utterance.rate = 0.95;
    utterance.pitch = 1.05;

    const voices = window.speechSynthesis.getVoices();
    const koVoice = voices.find(v => v.lang === 'ko-KR');
    if (koVoice) utterance.voice = koVoice;

    utterance.onend = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };

    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
    setIsPaused(false);
  };

  const togglePauseTTS = () => {
    if (isSpeaking) {
      if (isPaused) {
        window.speechSynthesis.resume();
        setIsPaused(false);
      } else {
        window.speechSynthesis.pause();
        setIsPaused(true);
      }
    }
  };

  const stopNarrativeTTS = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
  };

  const handlePhotoChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setReportPhotoBase64(event.target.result);
        setReportPhotoPreview(event.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGPSRequest = () => {
    if (navigator.geolocation) {
      showToast('📍 GPS 좌표 정보를 요청하는 중...');
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setReportLat(pos.coords.latitude.toFixed(6));
          setReportLng(pos.coords.longitude.toFixed(6));
          showToast('✅ 위치가 정상 반영되었습니다.');
        },
        () => {
          showToast('❌ GPS 위치 정보 획득 실패. 기본 좌표로 대체합니다.');
        }
      );
    } else {
      showToast('❌ 이 브라우저는 Geolocation을 지원하지 않습니다.');
    }
  };

  const handleReportSubmit = async (e) => {
    e.preventDefault();
    if (!reportName.trim() || !reportAddress.trim()) {
      showToast('필수 필드(제보명, 주소)를 채워주세요.');
      return;
    }
    showToast('📁 시민 제보 등록 중...');
    
    let imageUrl = '';
    if (reportPhotoBase64) {
      try {
        const uploadRes = await uploadImageToSupabaseStorage(
          reportPhotoBase64,
          `cit_${Date.now()}_${reportName.replace(/\s+/g, '')}.jpg`
        );
        if (uploadRes.status === 'success') {
          imageUrl = uploadRes.publicUrl;
        }
      } catch (err) {
        console.warn("Storage upload failed, fallback direct submit.");
      }
    }

    const payload = {
      name: reportName,
      address: reportAddress,
      description: reportReason,
      latitude: parseFloat(reportLat),
      longitude: parseFloat(reportLng),
      image_url: imageUrl,
      user_id: 'user@sejong.go.kr',
      status: '대기',
      recommend_count: 1,
      heart: 1
    };

    try {
      const res = await submitCitizenRecommendation(payload);
      if (res.status === 'success') {
        showToast('🌱 시민 제보가 성공적으로 등록되었습니다.');
        setReportName('');
        setReportAddress('');
        setReportReason('');
        setReportPhotoPreview('');
        setReportPhotoBase64('');
        loadAppData();
        setCurrentTab('home');
      } else {
        showToast('❌ 제보 등록 중 에러가 발생했습니다.');
      }
    } catch (err) {
      showToast('❌ 제보 제출 실패.');
    }
  };

  // 3. Render HTML
  return (
    <div className="mobile-frame-wrapper">
      {/* Toast popup alerts container */}
      <div style={{ position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)', zIndex: 9999, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {toastMessages.map(t => (
          <div key={t.id} style={{ background: 'rgba(9, 13, 22, 0.9)', color: '#00f5d4', border: '1px solid #00f5d4', padding: '10px 20px', borderRadius: '10px', fontSize: '0.85rem', boxShadow: '0 4px 12px rgba(0,245,212,0.2)' }}>
            {t.message}
          </div>
        ))}
      </div>

      <div className="mobile-device-chassis">
        {/* Device Status Bar */}
        <div style={{ height: '24px', background: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 18px', fontSize: '0.72rem', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
          <span>19:00 📱</span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <span>📶</span>
            <span>🔋 100%</span>
          </div>
        </div>

        <div className="mobile-app-content">
          {/* Header */}
          <header style={{ padding: '14px 16px', background: 'rgba(11, 15, 25, 0.9)', borderBottom: '1px solid rgba(0, 245, 212, 0.25)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.4rem' }}>🇰🇷</span>
            <div>
              <h1 style={{ fontSize: '1.05rem', fontWeight: 900, margin: 0, background: 'linear-gradient(135deg, #00f5d4, #38bdf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                전국 스마트 문화유산 ver_02
              </h1>
              <span style={{ fontSize: '0.6rem', color: '#64748b', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                National Heritage Platform
              </span>
            </div>
          </header>

          {/* Main App Content Viewport */}
          <main style={{ padding: '16px', flex: 1, overflowY: 'auto' }}>
            {currentTab === 'home' && (
              <>
                {/* AI RAG query cards search banner */}
                <section className="glass-card" style={{ padding: '18px', marginBottom: '20px' }}>
                  <h3 style={{ margin: '0 0 6px 0', fontSize: '1.1rem', color: '#fff' }}>🏛️ 인공지능 지리기반 유산 매칭 검색</h3>
                  <p style={{ margin: '0 0 12px 0', fontSize: '0.8rem', color: 'var(--text-sub)' }}>AI 비서와 함께 가보고 싶은 사찰, 정자, 역사지를 최적화 코스로 찾아보세요.</p>
                  
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input 
                      type="text" 
                      placeholder="사찰 관련 유산 추천해줘" 
                      value={ragQuery}
                      onChange={e => setRagQuery(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleRAGSearch()}
                      style={{ flex: 1, padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: '#111520', color: '#fff', fontSize: '0.85rem', outline: 'none' }}
                    />
                    <button onClick={handleRAGSearch} className="btn-primary" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
                      {ragLoading ? '검색중..' : '🔍 RAG 추천'}
                    </button>
                  </div>

                  {ragOutputText && (
                    <div style={{ marginTop: '12px', padding: '10px', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '0.78rem', color: '#93c5fd', borderLeft: '3px solid #3b82f6' }}>
                      {ragOutputText}
                    </div>
                  )}
                </section>

                {/* Map Component Viewer */}
                <section style={{ height: '280px', marginBottom: '20px', borderRadius: '16px', overflow: 'hidden' }}>
                  <MapComponent courseList={courseList.length > 0 ? courseList : ragCards} />
                </section>

                {/* AI Recommended Items Cards list */}
                <section style={{ marginBottom: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#fff' }}>🤖 AI 추천 문화유산 코스</h4>
                    {ragCards.length > 0 && (
                      <button onClick={() => addAllToCourse(ragCards)} style={{ background: 'none', border: 'none', color: '#00f5d4', fontSize: '0.75rem', fontWeight: 800, cursor: 'pointer' }}>
                        + 전체 코스에 담기
                      </button>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {ragCards.map(item => (
                      <div key={item.id} className="glass-card" style={{ padding: '12px', display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <img src={item.image_url} alt={item.name} style={{ width: '60px', height: '60px', borderRadius: '8px', objectFit: 'cover' }} />
                        <div style={{ flex: 1 }}>
                          <h5 style={{ margin: '0 0 3px 0', fontSize: '0.85rem', color: '#fff' }}>{item.name}</h5>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'block', marginBottom: '3px' }}>📍 {item.address}</span>
                          <span style={{ fontSize: '0.7rem', padding: '1px 5px', background: 'rgba(0, 245, 212, 0.1)', color: '#00f5d4', borderRadius: '4px', display: 'inline-block' }}>{item.category}</span>
                        </div>
                        <button onClick={() => addToCourse(item)} style={{ background: 'rgba(0,245,212,0.1)', border: '1px solid #00f5d4', color: '#00f5d4', padding: '4px 8px', borderRadius: '6px', fontSize: '0.72rem', cursor: 'pointer', fontWeight: 700 }}>
                          + 추가
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                {/* AI Multi-Agent Storytelling Guidebook creator area */}
                {courseList.length > 0 && (
                  <section className="glass-card" style={{ padding: '18px', background: 'linear-gradient(135deg, rgba(251,191,36,0.12), rgba(15,23,42,0.75))', border: '1px solid rgba(251,191,36,0.4)', marginBottom: '20px' }}>
                    <h4 style={{ margin: '0 0 6px 0', fontSize: '0.98rem', color: '#fbbf24' }}>📖 내 코스 맞춤 스토리북 제작</h4>
                    <p style={{ margin: '0 0 12px 0', fontSize: '0.75rem', color: 'var(--text-sub)' }}>설계하신 코스로 엄마가 들려주는 오디오 동화책과 가이드북을 자동 컴파일합니다.</p>
                    <button onClick={handleCreateGuidebook} className="btn-primary" style={{ width: '100%', padding: '10px', background: 'linear-gradient(135deg, #fbbf24, #d97706)', color: '#000', fontWeight: 900, border: 'none' }}>
                      {guidebookLoading ? '에이전트 협업 스토리북 생성 중...' : '✨ AI 스토리 가이드북 만들기'}
                    </button>
                  </section>
                )}

                {/* Generated Guidebook section */}
                {guidebookResult && (
                  <section ref={guidebookRef} className="glass-card" style={{ padding: '18px', border: '1px solid var(--accent-cyan)' }}>
                    <h3 style={{ margin: '0 0 10px 0', fontSize: '1.05rem', color: '#00f5d4' }}>🎙️ 엄마의 아늑한 구연동화 책방</h3>

                    {/* Audio controller block */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(0,245,212,0.05)', borderRadius: '8px', marginBottom: '14px' }}>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{ fontSize: '1.2rem' }}>🔊</span>
                        <div>
                          <strong style={{ fontSize: '0.8rem', color: '#fff', display: 'block' }}>여성 아나운서 보이스 TTS</strong>
                          <span style={{ fontSize: '0.65rem', color: '#00f5d4' }}>
                            {isSpeaking ? (isPaused ? '⏸️ 일시 정지' : '🔊 스토리북 낭독 중...') : '⏸️ 재생 준비 완료'}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '6px' }}>
                        {isSpeaking ? (
                          <>
                            <button onClick={togglePauseTTS} className="btn-secondary" style={{ padding: '6px 10px', fontSize: '0.7rem' }}>
                              {isPaused ? '▶️ 재개' : '⏸️ 일시정지'}
                            </button>
                            <button onClick={stopNarrativeTTS} className="btn-secondary" style={{ padding: '6px 10px', fontSize: '0.7rem', color: '#f43f5e', borderColor: '#f43f5e' }}>
                              ⏹️ 정지
                            </button>
                          </>
                        ) : (
                          <button onClick={startNarrativeTTS} className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.72rem', background: '#00f5d4', color: '#000' }}>
                            ▶️ 낭독 시작
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Story card blocks */}
                    <div style={{ display: 'flex', gap: '12px', overflowX: 'auto', paddingBottom: '10px', marginBottom: '16px' }}>
                      {guidebookResult.storyboard_cards?.map((card, i) => (
                        <div key={i} style={{ minWidth: '220px', maxWidth: '220px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '10px' }}>
                          <img src={card.image_url} alt={card.name} style={{ width: '100%', height: '110px', borderRadius: '6px', objectFit: 'cover', marginBottom: '6px' }} />
                          <h4 style={{ margin: '0 0 2px 0', fontSize: '0.8rem', color: '#fff' }}>{card.name}</h4>
                          <p style={{ margin: '0 0 6px 0', fontSize: '0.7rem', color: 'var(--text-sub)' }}>{card.scene_title}</p>
                          <div style={{ padding: '6px', background: 'rgba(0,245,212,0.05)', borderRadius: '4px', fontSize: '0.68rem', color: '#a7f3d0' }}>
                            💡 {card.guide_tip}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Rich text article output */}
                    <div style={{ background: '#0b0f19', padding: '14px', borderRadius: '10px', fontSize: '0.82rem', color: '#cbd5e1', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                      <h4 style={{ margin: '0 0 10px 0', color: '#fbbf24', fontSize: '0.9rem' }}>📝 상세 가이드 원고</h4>
                      {guidebookResult.guidebook_ko_article}
                      <hr style={{ borderColor: 'rgba(255,255,255,0.06)', margin: '14px 0' }} />
                      <h4 style={{ margin: '0 0 10px 0', color: '#38bdf8', fontSize: '0.9rem' }}>🇺🇸 English Translation</h4>
                      {guidebookResult.guidebook_en_article}
                    </div>
                  </section>
                )}
              </>
            )}

            {currentTab === 'course' && (
              <>
                <h2 style={{ fontSize: '1.25rem', color: '#fff', margin: '0 0 4px 0' }}>🗺️ 나만의 맞춤 코스 설계</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-sub)', margin: '0 0 16px 0' }}>선택하신 목적지 순서를 조정하고, 예상 소요 시간을 예측하여 여행을 계획하세요.</p>

                <div style={{ height: '240px', marginBottom: '20px', borderRadius: '16px', overflow: 'hidden' }}>
                  <MapComponent courseList={courseList} />
                </div>

                <div className="glass-card" style={{ padding: '16px', marginBottom: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <strong style={{ fontSize: '0.88rem', color: '#fff' }}>목적지 목록 ({courseList.length}개)</strong>
                    {courseList.length > 0 && (
                      <button onClick={() => setCourseList([])} style={{ background: 'none', border: 'none', color: '#f43f5e', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
                        🗑️ 전체 비우기
                      </button>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', marginBottom: '14px' }}>
                    {courseList.length === 0 ? (
                      <div style={{ color: 'var(--text-sub)', fontSize: '0.8rem', textAlign: 'center', padding: '20px 0' }}>
                        추가된 문화유산이 없습니다. 메인 탭에서 코스를 빌드하세요.
                      </div>
                    ) : (
                      courseList.map((item, idx) => (
                        <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.2)', padding: '8px 12px', borderRadius: '6px' }}>
                          <span style={{ fontSize: '0.8rem', color: '#fff', fontWeight: 600 }}>{idx + 1}. {item.name}</span>
                          <button onClick={() => setCourseList(prev => prev.filter(c => c.id !== item.id))} style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer', fontSize: '0.78rem' }}>
                            삭제
                          </button>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Transport & duration calculation widget */}
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '12px' }}>
                    <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'block', marginBottom: '4px' }}>🚗 교통 수단 선택</label>
                    <select 
                      value={transport} 
                      onChange={e => setTransport(e.target.value)}
                      style={{ width: '100%', padding: '8px 10px', background: '#111520', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '6px', fontSize: '0.82rem', outline: 'none', marginBottom: '12px' }}
                    >
                      <option value="승용차">🚗 승용차 (자가용)</option>
                      <option value="대중교통">🚌 대중교통 / 버스</option>
                      <option value="도보">🚶 도보 / 자전거</option>
                    </select>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,245,212,0.06)', padding: '10px 14px', borderRadius: '8px' }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-sub)' }}>⏱️ 예상 총 소요시간:</span>
                      <strong style={{ fontSize: '1.05rem', color: '#00f5d4' }}>약 {totalTimeText}</strong>
                    </div>
                  </div>
                </div>
              </>
            )}

            {currentTab === 'report' && (
              <>
                <h2 style={{ fontSize: '1.25rem', color: '#fff', margin: '0 0 4px 0' }}>🌱 시민 제보 및 GPS 위치 등록</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-sub)', margin: '0 0 16px 0' }}>세종시의 숨겨진 보물이나 훼손 위험이 있는 문화유산을 실시간 제보해 주세요.</p>

                <form onSubmit={handleReportSubmit} className="glass-card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#fff', display: 'block', marginBottom: '4px' }}>유산 제보명 *</label>
                    <input 
                      type="text" 
                      placeholder="예: 다방리 은행나무" 
                      value={reportName}
                      onChange={e => setReportName(e.target.value)}
                      required
                      style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', background: '#111520', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '6px', fontSize: '0.8rem', outline: 'none' }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#fff', display: 'block', marginBottom: '4px' }}>지리 주소 *</label>
                    <input 
                      type="text" 
                      placeholder="예: 세종특별자치시 전의면 다방길" 
                      value={reportAddress}
                      onChange={e => setReportAddress(e.target.value)}
                      required
                      style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', background: '#111520', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '6px', fontSize: '0.8rem', outline: 'none' }}
                    />
                  </div>

                  {/* Geolocation properties */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'block', marginBottom: '3px' }}>위도 (Lat)</label>
                      <input type="text" value={reportLat} readOnly style={{ width: '100%', boxSizing: 'border-box', padding: '6px 8px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', color: '#cbd5e1', borderRadius: '6px', fontSize: '0.75rem' }} />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.72rem', color: 'var(--text-sub)', display: 'block', marginBottom: '3px' }}>경도 (Lng)</label>
                      <input type="text" value={reportLng} readOnly style={{ width: '100%', boxSizing: 'border-box', padding: '6px 8px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', color: '#cbd5e1', borderRadius: '6px', fontSize: '0.75rem' }} />
                    </div>
                  </div>

                  <button type="button" onClick={handleGPSRequest} style={{ background: 'rgba(56,189,248,0.1)', border: '1px solid #38bdf8', color: '#38bdf8', padding: '8px', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 700 }}>
                    📍 현 위치 GPS 좌표 가져오기
                  </button>

                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#fff', display: 'block', marginBottom: '4px' }}>제보 사유 / 설명</label>
                    <textarea 
                      placeholder="역사 문화적 보존 필요성 혹은 아름다운 정경을 적어주세요." 
                      value={reportReason}
                      onChange={e => setReportReason(e.target.value)}
                      rows={3}
                      style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', background: '#111520', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '6px', fontSize: '0.8rem', outline: 'none', resize: 'none' }}
                    />
                  </div>

                  {/* Photo Uploader */}
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#fff', display: 'block', marginBottom: '4px' }}>현장 사진 첨부</label>
                    <input 
                      type="file" 
                      accept="image/*"
                      onChange={handlePhotoChange}
                      style={{ fontSize: '0.75rem', color: 'var(--text-sub)' }}
                    />
                    {reportPhotoPreview && (
                      <img src={reportPhotoPreview} alt="Preview" style={{ width: '100%', height: '140px', objectFit: 'cover', borderRadius: '8px', marginTop: '10px' }} />
                    )}
                  </div>

                  <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '8px' }}>
                    🌱 제보 등록 제출하기
                  </button>
                </form>
              </>
            )}
          </main>

          {/* Bottom Navigation Bar */}
          <nav style={{ height: '56px', background: '#090d16', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', alignItems: 'center', textAlign: 'center' }}>
            <div 
              onClick={() => setCurrentTab('home')} 
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '3px', color: currentTab === 'home' ? '#00f5d4' : '#64748b' }}
            >
              <span style={{ fontSize: '1.15rem' }}>🏛️</span>
              <span style={{ fontSize: '0.65rem', fontWeight: 700 }}>홈 / 추천</span>
            </div>
            <div 
              onClick={() => setCurrentTab('course')} 
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '3px', color: currentTab === 'course' ? '#00f5d4' : '#64748b' }}
            >
              <span style={{ fontSize: '1.15rem' }}>🗺️</span>
              <span style={{ fontSize: '0.65rem', fontWeight: 700 }}>코스 설계</span>
            </div>
            <div 
              onClick={() => setCurrentTab('report')} 
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '3px', color: currentTab === 'report' ? '#00f5d4' : '#64748b' }}
            >
              <span style={{ fontSize: '1.15rem' }}>🌱</span>
              <span style={{ fontSize: '0.65rem', fontWeight: 700 }}>시민 제보</span>
            </div>
          </nav>
        </div>
      </div>
    </div>
  );
}
