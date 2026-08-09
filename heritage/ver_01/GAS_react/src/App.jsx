import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import JSZip from 'jszip';
import MapComponent from './components/MapComponent';
import {
  fetchInitialAppData,
  syncHeartToSupabase,
  submitCitizenRecommendation,
  saveCourse,
  fetchSavedCourses,
  submitCourseReview,
  fetchKorServiceOpenAPI,
  queryAgenticRAG,
  generateGuidebook,
  fetchAgenticGraph,
  uploadImageToSupabase,
} from './api';

// Helper function to clean image URLs
function fixHttpsUrl(url) {
  if (!url) return '';
  let clean = url.trim();
  if (clean.startsWith('http://')) {
    clean = clean.replace('http://', 'https://');
  }
  return clean;
}

// 1. getStandardHeritageImage
function getStandardHeritageImage(item, officialHeritages = []) {
  if (!item) return { url: '', source: '일반', tier: 0 };

  const raw = item.rawObj || item;
  const name = String(item.name || item.title || raw.name || raw.title || '').trim();
  const qName = name.toLowerCase();

  // Tier 1: Supabase DB / Storage images
  let t1Url = '';
  if (raw.images && Array.isArray(raw.images) && raw.images.length > 0) {
    t1Url = fixHttpsUrl(raw.images[0].image_url || raw.images[0].imageUrl || '');
  }
  if (!t1Url) {
    const rawDirect = item.image_url || item.photo_url || raw.image_url || raw.photo_url || raw.supabase_storage_url;
    const dUrl = fixHttpsUrl(rawDirect);
    if (dUrl && (dUrl.includes('supabase.co') || dUrl.includes('heritage-images'))) {
      t1Url = dUrl;
    }
  }
  if (!t1Url && officialHeritages.length > 0) {
    const offMatch = officialHeritages.find(o => {
      const oName = String(o.name || '').toLowerCase().trim();
      return oName && qName && (qName.includes(oName) || oName.includes(qName));
    });
    if (offMatch) {
      t1Url = fixHttpsUrl(offMatch.image_url || offMatch.photo_url || offMatch.supabase_storage_url);
    }
  }
  if (!t1Url) {
    const hId = item.h_id || raw.h_id;
    if (hId && typeof hId === 'string' && hId.startsWith('H')) {
      t1Url = `https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/${hId}_${hId}.jpg`;
    }
  }
  if (!t1Url) {
    const knownMap = [
      { kw: '비암사', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H1_H1.jpg' },
      { kw: '연기아문', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H2_H2.jpg' },
      { kw: '전의초수', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H3_H3.jpg' },
      { kw: '이유태', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H4_H4.jpg' },
      { kw: '합강정', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H5_H5.jpg' },
      { kw: '독락정', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H6_H6.jpg' },
      { kw: '운주산성', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H7_H7.jpg' },
      { kw: '임난수', url: 'https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H8_H8.jpg' }
    ];
    for (let k = 0; k < knownMap.length; k++) {
      if (qName.includes(knownMap[k].kw)) {
        t1Url = knownMap[k].url;
        break;
      }
    }
  }

  if (t1Url && t1Url.length > 10 && !t1Url.includes('unsplash.com')) {
    return { url: t1Url, source: '🏛️ Supabase Storage DB 이미지', tier: 1 };
  }

  // Tier 2: Web image fallback
  const webRaw = item.web_image_url || item.web_photo || item.thumbnail || item.firstimage || item.firstimage2;
  const webUrl = fixHttpsUrl(webRaw);
  if (webUrl && webUrl.length > 10 && !webUrl.includes('supabase.co') && !webUrl.includes('unsplash.com')) {
    let sourceLabel = '🌐 웹 이미지';
    if (webUrl.includes('naver.net') || webUrl.includes('naver.com')) sourceLabel = '🍀 네이버 이미지';
    else if (webUrl.includes('google') || webUrl.includes('ggpht')) sourceLabel = '🔍 구글 이미지';
    else if (webUrl.includes('wikimedia') || webUrl.includes('wikipedia')) sourceLabel = '📖 위키백과 이미지';
    
    return { url: webUrl, source: sourceLabel, tier: 2 };
  }

  // Random Fallback
  let hash = 0;
  for (let i = 0; i < qName.length; i++) {
    hash = qName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const imgNum = (Math.abs(hash) % 8) + 1;
  const fallbackUrl = `https://pdpmtgnagwzcsftavtap.supabase.co/storage/v1/object/public/heritage-images/H${imgNum}_H${imgNum}.jpg`;
  
  return { url: fallbackUrl, source: '🏛️ Supabase Storage DB 이미지', tier: 1 };
}

// 2. normalizeHeritage
function normalizeHeritage(item, officialHeritages = [], likesMap = {}) {
  if (!item) return null;
  const name = item.name || item.heritage_name || item.title || '세종 문화유산';
  const address = item.address || item.dong_eup_myeon || item.location || '대한민국';
  
  // Exctract dong
  let dong = item.dong_eup_myeon || '세종시';
  if (address.includes('연기면')) dong = '연기면';
  else if (address.includes('전의면')) dong = '전의면';
  else if (address.includes('어진동')) dong = '어진동';
  else if (address.includes('연동면')) dong = '연동면';
  else if (address.includes('금남면')) dong = '금남면';
  else if (address.includes('장군면')) dong = '장군면';

  const category = item.category || item.era_normalized || item.era || '조선시대';
  const description = item.description || item.reason || item.content || '대한민국에 위치한 아름다운 문화유산입니다.';
  const id = item.id || item.h_id || `h_${Math.random().toString(36).substr(2, 9)}`;
  
  let likes = typeof item.like_count === 'number' ? item.like_count : 50;
  if (likesMap[id]) {
    likes += likesMap[id];
  }

  const imgInfo = getStandardHeritageImage(item, officialHeritages);

  return {
    id,
    name,
    category,
    era: category,
    era_normalized: category,
    dong_eup_myeon: dong,
    dong,
    address,
    description,
    image_url: imgInfo.url,
    photo_url: imgInfo.url,
    image_source: imgInfo.source,
    like_count: likes,
    parking_yn: item.parking_yn || 'Y',
    restroom_yn: item.restroom_yn || 'Y',
    lat: parseFloat(item.lat || item.mapy || item.latitude || 36.48),
    lng: parseFloat(item.lng || item.mapx || item.longitude || 127.28),
    rawObj: item
  };
}

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
  // TTS Speech States
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTab, setCurrentTab] = useState('home');
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  const [officialHeritages, setOfficialHeritages] = useState([]);
  const [citizenHeritages, setCitizenHeritages] = useState([]);
  const [courseList, setCourseList] = useState([]);
  const [savedCourses, setSavedCourses] = useState([]);
  const [likesMap, setLikesMap] = useState({});
  const [selectedHeritageDetail, setSelectedHeritageDetail] = useState(null);
  const [toastMessages, setToastMessages] = useState([]);
  const [statusSubTab, setStatusSubTab] = useState('official');
  const [showDetailOverlay, setShowDetailOverlay] = useState(false);
  

  // Modal States
  const [showCitizenReportModal, setShowCitizenReportModal] = useState(false);
  const [showSaveCourseModal, setShowSaveCourseModal] = useState(false);
  const [showLoadRoutesModal, setShowLoadRoutesModal] = useState(false);

  // RAG States
  const [selectedRegion, setSelectedRegion] = useState('전체');
  const [ragQuery, setRagQuery] = useState('');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragNode, setRagNode] = useState(null); // 'start', 'rewrite', 'rag', 'analysis', 'output'
  const [homeRecommendedCards, setHomeRecommendedCards] = useState([]);
  const [ragOutputText, setRagOutputText] = useState('');

  // Course Planner States
  const [courseTransport, setCourseTransport] = useState('승용차');
  const [courseTotalTimeText, setCourseTotalTimeText] = useState('0분');
  const [nearbyHeritages, setNearbyHeritages] = useState([]);

  // Guidebook States
  const [guidebookLoading, setGuidebookLoading] = useState(false);
  const [guidebookResult, setGuidebookResult] = useState(null);
  const [guidebookStepsLog, setGuidebookStepsLog] = useState([]);

  // Korea Tourism OpenAPI States
  const [korServiceOp, setKorServiceOp] = useState('searchKeyword2');
  const [korServiceArrange, setKorServiceArrange] = useState('A');
  const [korServiceKeyword, setKorServiceKeyword] = useState('세종');
  const [korServiceLoading, setKorServiceLoading] = useState(false);
  const [korServiceCards, setKorServiceCards] = useState([]);
  const [korServiceRawJson, setKorServiceRawJson] = useState({});
  const [korServiceViewMode, setKorServiceViewMode] = useState('card');

  // Citizen report Form States
  const [citFormName, setCitFormName] = useState('');
  const [citFormAddress, setCitFormAddress] = useState('');
  const [citFormLat, setCitFormLat] = useState('36.4800');
  const [citFormLng, setCitFormLng] = useState('127.2800');
  const [citFormReason, setCitFormReason] = useState('');
  const [citFormPhotoPreview, setCitFormPhotoPreview] = useState('');
  const [citFormPhotoBase64, setCitFormPhotoBase64] = useState('');

  // Search Screen Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [searchDong, setSearchDong] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Admin Screen States
  
  
  
  
  
  
  

  // References
  
  
  const guidebookContainerRef = useRef(null);

  const addHeritageToCourseInPlace = (item) => {
    const norm = normalizeHeritage(item, officialHeritages, likesMap);
    if (courseList.some(c => c.id === norm.id)) {
      showToast('이미 코스에 추가되어 있습니다.');
    } else {
      setCourseList(prev => [...prev, norm]);
      showToast(`\U0001f9ed '${norm.name}' 유산이 코스에 담겼습니다. (현재 총 ${courseList.length + 1}개)`);
    }
  };

  const addHeritageToCourseAndRedirect = (item) => {
    const norm = normalizeHeritage(item, officialHeritages, likesMap);
    if (courseList.some(c => c.id === norm.id)) {
      showToast('이미 코스에 추가되었습니다.');
    } else {
      setCourseList(prev => [...prev, norm]);
      showToast(`🧭 '${norm.name}' 유산을 코스에 추가했습니다.`);
    }
    setCurrentTab('course');
  };

  // Announcer Voice TTS Storytelling handlers
  const startStorytellingTTS = () => {
    if (!guidebookResult || !guidebookResult.final_output) return;
    window.speechSynthesis.cancel();

    // Clean markdown elements for text speech synthesis
    const cleanText = guidebookResult.final_output
      .replace(/###/g, '')
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/📌/g, '')
      .replace(/💡/g, '')
      .replace(/-/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'ko-KR';
    utterance.rate = 0.95; // Cozy reading rate
    utterance.pitch = 1.05; // Slightly higher friendly pitch

    const voices = window.speechSynthesis.getVoices();
    const koVoice = voices.find(v => v.lang === 'ko-KR' && (v.name.includes('Yuna') || v.name.includes('Google') || v.name.includes('Heami') || v.name.includes('Female')));
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

  const pauseStorytellingTTS = () => {
    window.speechSynthesis.pause();
    setIsPaused(true);
  };

  const resumeStorytellingTTS = () => {
    window.speechSynthesis.resume();
    setIsPaused(false);
  };

  const stopStorytellingTTS = () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
  };

  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
    };
  }, []);

  // Initialize Data
  useEffect(() => {
    loadInitialData();
  }, []);

  // Sync Course Planner Total Time
  useEffect(() => {
    calculateCourseTime();
  }, [courseList, courseTransport]);

  // Sync Search Results
  useEffect(() => {
    executeSearch();
  }, [officialHeritages, citizenHeritages]);

  const showToast = (message) => {
    const id = Date.now() + Math.random();
    setToastMessages(prev => [...prev, { id, message }]);
    setTimeout(() => {
      setToastMessages(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  const loadInitialData = async () => {
    try {
      showToast('⏳ 초기 데이터를 불러오는 중...');
      const initData = await fetchInitialAppData();
      
      const hData = initData.official || [];
      const normHeritages = hData.map(item => normalizeHeritage(item, hData, likesMap));
      setOfficialHeritages(normHeritages.filter(h => h.rawObj.source !== 'citizen'));
      
      const cData = initData.citizen || [];
      const normCitizen = cData.map(item => ({
        id: item.id || `cit_${item.name}`,
        name: item.name,
        address: item.address || item.dong || '세종시',
        dong: item.address || item.dong || '세종시',
        dong_eup_myeon: item.address || item.dong || '세종시',
        lat: parseFloat(item.latitude || item.lat) || 36.48,
        lng: parseFloat(item.longitude || item.lng) || 127.28,
        reason: item.description || '시민 제보 문화유산',
        description: item.description || '시민 제보 문화유산',
        image_url: item.photo_url || item.image_url || '',
        status: item.status || '대기',
        like_count: item.heart || item.recommend_count || 1,
        submitted_by: item.user_id || 'user@sejong.go.kr'
      }));
      setCitizenHeritages(normCitizen);
      setAdminSubmissions(normCitizen);

      // Load mock/predefined admin reviews
      setAdminReviews([
        { heritageName: '조치원향교', rating: 5, text: '조용하고 인접 주차 공간이 잘 정비되어 탐방하기 원활합니다.', isImprovementNeeded: false },
        { heritageName: '연기아문', rating: 3, text: '역사적 보존 가치는 매우 높으나 야간 조명 설치 개선이 필요해 보입니다.', isImprovementNeeded: true },
        { heritageName: '비암사', rating: 5, text: '극락보전 괘불탱의 아름다움과 숲길 산책로 조성이 환상적입니다.', isImprovementNeeded: false }
      ]);
      
      // Load saved courses
      const saved = await fetchSavedCourses();
      setSavedCourses(saved);

      // Fill nearby recommendations
      if (normHeritages.length > 0) {
        setNearbyHeritages(normHeritages.slice(0, 8));
      }
    } catch (err) {
      showToast('⚠️ 데이터를 가져오는 중 오류가 발생했습니다.');
    }
  };

  const calculateCourseTime = () => {
    if (courseList.length === 0) {
      setCourseTotalTimeText('0분');
      return;
    }
    const perSiteMinutes = 30; // 30 mins per site
    const travelMinutesPerLeg = (courseTransport === '도보') ? 50 : (courseTransport === '대중교통') ? 30 : 15;
    const totalMinutes = (courseList.length * perSiteMinutes) + (Math.max(0, courseList.length - 1) * travelMinutesPerLeg);
    
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    setCourseTotalTimeText(hours > 0 ? `${hours}시간 ${mins}분` : `${mins}분`);
  };

  const executeSearch = () => {
    const list = [...officialHeritages, ...citizenHeritages.filter(c => c.status === '승인')];
    const filtered = list.filter(h => {
      const q = searchQuery.toLowerCase().trim();
      const matchQuery = !q || h.name.toLowerCase().includes(q) || h.address.toLowerCase().includes(q) || h.category.toLowerCase().includes(q) || h.description.toLowerCase().includes(q);
      const matchDong = !searchDong || h.dong_eup_myeon.includes(searchDong) || h.address.includes(searchDong);
      return matchQuery && matchDong;
    });
    setSearchResults(filtered);
  };

  // Agentic RAG Simulation/Request
  const sendHomeAgenticRAGRequest = async () => {
    if (!ragQuery.trim()) {
      showToast('추천 쿼리를 입력해 주세요.');
      return;
    }
    setRagLoading(true);
    setRagNode('start');
    setRagOutputText('');
    setHomeRecommendedCards([]);

    // Progress updates simulation
    const steps = [
      { node: 'rewrite', delay: 1000 },
      { node: 'rag', delay: 2000 },
      { node: 'analysis', delay: 3500 },
      { node: 'output', delay: 5000 }
    ];

    steps.forEach(step => {
      setTimeout(() => {
        setRagNode(step.node);
      }, step.delay);
    });

    try {
      const regionOpt = REGION_OPTIONS.find(opt => opt.code === selectedRegion);
      const regionName = regionOpt && regionOpt.code !== '전체' ? regionOpt.name.split('(')[0].trim() : '';
      const combinedQuery = regionName ? `${regionName} ${ragQuery.trim()}` : ragQuery.trim();

      const data = await queryAgenticRAG(combinedQuery, selectedRegion);
      setTimeout(() => {
        setRagLoading(false);
        setRagNode(null);
        if (data.output_heritages) {
          const matched = data.output_heritages.map(item => normalizeHeritage(item, officialHeritages));
          setHomeRecommendedCards(matched);
        }
        setRagOutputText(data.final_output || 'AI 추천 결과 도출이 완료되었습니다.');
        showToast('✅ AI 추천 완료!');
      }, 5500);
    } catch (err) {
      console.warn('FastAPI RAG error, calling simulated RAG:', err);
      // Simulated Fallback
      setTimeout(() => {
        setRagLoading(false);
        setRagNode(null);
        const fallbackList = officialHeritages.slice(0, 5);
        setHomeRecommendedCards(fallbackList);
        setRagOutputText(`### [AI 에이전트 분석 보고서]\n\n대한민국의 역사 유적지 추천 결과:\n\n1. **비암사** (조선시대)\n2. **연기아문** (조선시대)\n3. **전의초수** (조선시대)\n4. **초려 이유태 묘소** (조선시대)\n5. **세종 합강정** (현대)\n\n위 문화유산들을 거쳐 갈 때 가장 매력적인 역사 탐방 동선을 연출할 수 있습니다.`);
        showToast('✅ AI 추천 완료(로컬 시뮬레이션)');
      }, 5500);
    }
  };

  const copyRecommended5ToCourse = () => {
    if (homeRecommendedCards.length === 0) {
      showToast('추천 카드가 없습니다. 추천을 먼저 진행해 주세요.');
      return;
    }
    setCourseList(homeRecommendedCards);
    showToast('🗺️ 추천 5선이 당일 코스 빌더에 입력되었습니다!');
  };

  const generateGuidebookStoryboard = async () => {
    if (courseList.length === 0) {
      showToast('코스 빌더에 문화유산이 최소 1개 이상 필요합니다.');
      return;
    }
    setGuidebookLoading(true);
    setGuidebookResult(null);
    setGuidebookStepsLog([
      '🤖 [StateGraph Step 1] AI 프롬프트 분석 및 코스 정보 수집 중...',
      '🎨 [StateGraph Step 2] 에이전트 협업: 각 유산의 팁 작성 중...'
    ]);

    setTimeout(() => {
      setGuidebookStepsLog(prev => [...prev, '🗺️ [StateGraph Step 3] 백엔드 가이드북 생성 진행 중...']);
    }, 1500);

    const heritageNames = courseList.map(item => item.name);
    try {
      const data = await generateGuidebook(heritageNames, courseTransport);
      setGuidebookStepsLog(prev => [...prev, '✅ [StateGraph Complete] 스토리보드 SVG & 가이드북 도출 완료!']);
      setGuidebookResult(data);
      setGuidebookLoading(false);
      
      // Auto scroll to guidebook output
      setTimeout(() => {
        guidebookContainerRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
    } catch (err) {
      console.warn('Guidebook API error, generating local fallback:', err);
      // Fallback
      setTimeout(() => {
        setGuidebookStepsLog(prev => [...prev, '✅ [StateGraph Complete] 시뮬레이터 가이드북 도출 완료!']);
        setGuidebookResult({
          storyboard_cards: courseList.map((item, idx) => ({
            name: item.name,
            address: item.address,
            scene_title: `${item.name}의 역사적 정취를 찾아서`,
            guide_tip: item.description.slice(0, 100) + '...',
            image_url: item.image_url
          })),
          final_output: `[AI 협업 4대 에이전트 국/영문 가이드]\n\n세종 문화유산 코스 안내:\n${courseList.map((it, i) => `${i+1}. ${it.name} - ${it.address}`).join('\n')}`
        });
        setGuidebookLoading(false);
      }, 3000);
    }
  };

  // Korea Tourism OpenAPI Search
  const executeKorServiceSearch = async () => {
    setKorServiceLoading(true);
    setKorServiceCards([]);
    try {
      const data = await fetchKorServiceOpenAPI(korServiceOp, korServiceKeyword, korServiceArrange);
      setKorServiceRawJson(data);

      let rawItems = data?.response?.body?.items?.item || data?.items || [];
      if (rawItems && !Array.isArray(rawItems)) rawItems = [rawItems];
      
      setKorServiceCards(rawItems);
      setKorServiceLoading(false);
      showToast(`📡 OpenAPI 데이터 ${rawItems.length}건 로드 성공`);
    } catch (err) {
      setKorServiceLoading(false);
      showToast('❌ OpenAPI 데이터를 불러올 수 없습니다.');
    }
  };

  // Citizen submission actions
  const handleCitizenPhotoSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      setCitFormPhotoPreview(evt.target.result);
      setCitFormPhotoBase64(evt.target.result);
    };
    reader.readAsDataURL(file);
  };

  const acquireCurrentGPSLocation = () => {
    if (navigator.geolocation) {
      showToast('📍 GPS 좌표를 요청하는 중...');
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCitFormLat(position.coords.latitude.toFixed(6));
          setCitFormLng(position.coords.longitude.toFixed(6));
          showToast('✅ 현재 GPS 위치가 정상 반영되었습니다.');
        },
        (err) => {
          showToast('❌ GPS 정보 획득 실패. 기본 좌표로 대체합니다.');
        }
      );
    } else {
      showToast('❌ 이 브라우저는 Geolocation을 지원하지 않습니다.');
    }
  };

  const submitCitizenReport = async (e) => {
    e.preventDefault();
    if (!citFormName.trim() || !citFormAddress.trim()) {
      showToast('필수 필드를 채워주세요.');
      return;
    }
    
    showToast('📁 시민 제보 제출 및 이미지 업로드 처리 중...');
    
    let uploadedUrl = '';
    if (citFormPhotoBase64) {
      try {
        const uploadRes = await uploadImageToSupabase(citFormPhotoBase64, `cit_${Date.now()}_${citFormName}.jpg`);
        uploadedUrl = uploadRes.publicUrl;
      } catch (err) {
        console.warn('Image upload failed, submitting without image:', err);
      }
    }

    const payload = {
      name: citFormName,
      address: citFormAddress,
      description: citFormReason,
      latitude: parseFloat(citFormLat),
      longitude: parseFloat(citFormLng),
      image_url: uploadedUrl,
      user_id: 'user@sejong.go.kr',
      status: '대기',
      recommend_count: 1,
      heart: 1
    };

    try {
      await submitCitizenRecommendation(payload);
      showToast('🌱 시민 제보가 정상 등록되었습니다.');
      setCurrentTab('home');
      
      // Reset form
      setCitFormName('');
      setCitFormAddress('');
      setCitFormReason('');
      setCitFormPhotoPreview('');
      setCitFormPhotoBase64('');
      
      // Reload recommendations
      loadInitialData();
    } catch (err) {
      showToast('❌ 제보 등록 실패');
    }
  };

  const handleHeartClick = async (item) => {
    const newHeart = (item.like_count || item.heart || 0) + 1;
    showToast('❤️ 좋아요 처리 완료!');
    
    // Optimistic UI updates
    setCitizenHeritages(prev => prev.map(c => c.id === item.id ? { ...c, like_count: newHeart } : c));
    
    // Sync backend
    await syncHeartToSupabase(item.id, newHeart, item.name);
  };

  // Course management
  const handleSaveCourseSubmit = async (e) => {
    e.preventDefault();
    const titleInput = document.getElementById('saveCourseTitleInput')?.value || '';
    const memoInput = document.getElementById('saveCourseMemoInput')?.value || '';
    
    if (!titleInput.trim()) {
      showToast('코스 제목은 필수입니다.');
      return;
    }

    const payload = {
      user_id: 'user@sejong.go.kr',
      title: titleInput,
      transport_mode: courseTransport,
      total_duration_min: courseList.length * 30, // 30 min per site
      items: courseList
    };

    try {
      showToast('💾 코스를 DB에 저장하는 중...');
      await saveCourse(payload);
      showToast('✅ 코스가 Supabase DB에 안전하게 보관되었습니다!');
      setShowSaveCourseModal(false);
      
      // Reload courses
      const saved = await fetchSavedCourses();
      setSavedCourses(saved);
    } catch (err) {
      showToast('❌ 코스 저장 실패');
    }
  };

  const applySelectedSavedCourse = (course) => {
    if (course && course.items) {
      // Map supabase relation course_items back to normalized heritages
      const matched = course.items.map((it, idx) => {
        const found = [...officialHeritages, ...citizenHeritages].find(h => h.id === it.heritage_id);
        return found || {
          id: it.heritage_id,
          name: `지정 유산 ${it.heritage_id}`,
          address: '세종시',
          era: '조선시대',
          dong: '세종시'
        };
      });
      setCourseList(matched);
      if (course.guidebook_result) {
        setGuidebookResult(course.guidebook_result);
        showToast(`📂 '${course.title}' 코스와 AI 가이드북을 복원했습니다.`);
      } else {
        setGuidebookResult(null);
        showToast(`📂 '${course.title}' 코스를 적용했습니다.`);
      }
      setShowLoadRoutesModal(false);
    }
  };

  const renderActiveTab = () => {
    switch (currentTab) {
      case 'home':
        return (
          <>
            {/* Header section with AI query box */}
            <div className="glass-card" style={{ padding: '20px', marginBottom: '24px', background: 'rgba(15, 23, 42, 0.88)', border: '1px solid var(--accent-cyan)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', margin: 0 }}>🏛️ 전국 스마트 문화유산 지리기반 통합 서비스</h3>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-sub)', margin: 0 }}>AI 에이전트와 지도를 활용하여 최적의 문화유산 탐방 동선을 실시간으로 계산하고 시각화합니다.</p>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '10px' }}>
                  <select
                    value={selectedRegion}
                    onChange={(e) => setSelectedRegion(e.target.value)}
                    style={{
                      padding: '12px 16px',
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.5)',
                      border: '1px solid var(--accent-cyan)',
                      color: '#fff',
                      fontSize: '0.95rem',
                      outline: 'none',
                      cursor: 'pointer',
                      minWidth: '150px'
                    }}
                  >
                    {REGION_OPTIONS.map((opt) => (
                      <option key={opt.code} value={opt.code} style={{ background: '#1e293b', color: '#fff' }}>
                        {opt.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder="사찰 코스 추천해줘"
                    value={ragQuery}
                    onChange={(e) => setRagQuery(e.target.value)}
                    onKeyUp={(e) => e.key === 'Enter' && sendHomeAgenticRAGRequest()}
                    style={{ flex: 1, minWidth: '260px', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--accent-cyan)', color: '#fff', fontSize: '0.95rem', outline: 'none' }}
                  />
                  <button onClick={sendHomeAgenticRAGRequest} className="btn-primary" style={{ padding: '12px 24px', fontSize: '0.95rem', fontWeight: 800, background: 'linear-gradient(135deg, #00f5d4, #7209b7)', borderRadius: '10px', border: 'none' }}>
                    {ragLoading ? '추천 중...' : '🔍 RAG 최적화 추천'}
                  </button>
                </div>
              </div>

              {/* RAG Nodes loading steps */}
              {ragLoading && (
                <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(0,0,0,0.4)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '6px', fontSize: '0.72rem', textAlign: 'center' }}>
                    <div style={{ background: ragNode === 'start' ? 'rgba(0,245,212,0.15)' : 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '6px', borderRadius: '6px' }}>접수</div>
                    <div style={{ background: ragNode === 'rewrite' ? 'rgba(0,245,212,0.15)' : 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '6px', borderRadius: '6px' }}>재구성</div>
                    <div style={{ background: ragNode === 'rag' ? 'rgba(0,245,212,0.15)' : 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '6px', borderRadius: '6px' }}>벡터매칭</div>
                    <div style={{ background: ragNode === 'analysis' ? 'rgba(0,245,212,0.15)' : 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '6px', borderRadius: '6px' }}>심층분석</div>
                    <div style={{ background: ragNode === 'output' ? 'rgba(0,245,212,0.15)' : 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', padding: '6px', borderRadius: '6px' }}>가이드출력</div>
                  </div>
                </div>
              )}
            </div>

            {/* Split Screen layout: Map on the Left, Controls on the Right */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', alignItems: 'flex-start' }}>
              
              {/* Centerpiece Map Section */}
              <div className="glass-card" style={{ padding: '18px', height: '540px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justify: 'space-between', alignItems: 'center', marginBottom: '12px', justifyContent: 'space-between' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--accent-cyan)', margin: 0 }}>🗺️ 전국 스마트 문화유산 코스 경로 지도</h3>
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                    {courseList.length > 0 ? '🏁 생성 코스 표시 중' : '📍 추천 목록 표시 중'}
                  </span>
                </div>
                <div style={{ flex: 1, position: 'relative', minHeight: '380px' }}>
                  <MapComponent courseList={courseList.length > 0 ? courseList : (homeRecommendedCards.length > 0 ? homeRecommendedCards : officialHeritages.slice(0, 5))} />
                </div>
                
                {/* Course Path Indicator Bar */}
                <div style={{ marginTop: '12px', padding: '8px 12px', background: 'rgba(0,245,212,0.06)', borderRadius: '8px', border: '1px solid rgba(0,245,212,0.15)', overflowX: 'auto', whiteSpace: 'nowrap', display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <strong style={{ fontSize: '0.78rem', color: '#00f5d4', marginRight: '6px' }}>경로:</strong>
                  {(courseList.length > 0 ? courseList : homeRecommendedCards).length === 0 ? (
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>검색 추천 또는 선택된 경로 지점이 없습니다.</span>
                  ) : (
                    (courseList.length > 0 ? courseList : homeRecommendedCards).map((c, i) => (
                      <span key={i} style={{ fontSize: '0.78rem', color: '#fff', fontWeight: 700 }}>
                        {i + 1}. {c.name} {i < (courseList.length > 0 ? courseList : homeRecommendedCards).length - 1 && ' ➔ '}
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Course & Recommended Control Pane */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                {/* Selected Course List */}
                <div className="glass-card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justify: 'space-between', alignItems: 'center', marginBottom: '14px', justifyContent: 'space-between' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>🚩 내 탐방 코스 장소 ({courseList.length}개)</h3>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={() => setShowSaveCourseModal(true)} style={{ background: 'linear-gradient(135deg, #10b981, #00f5d4)', color: '#0f172a', fontWeight: 900, border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '0.78rem', cursor: 'pointer' }}>💾 저장</button>
                      <button onClick={() => setShowLoadRoutesModal(true)} style={{ background: 'rgba(56,189,248,0.15)', border: '1px solid #38bdf8', color: '#38bdf8', borderRadius: '6px', padding: '4px 10px', fontSize: '0.78rem', cursor: 'pointer' }}>📂 불러오기</button>
                      <button onClick={() => setCourseList([])} style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#f87171', borderRadius: '6px', padding: '4px 8px', fontSize: '0.75rem', cursor: 'pointer' }}>전체삭제</button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '160px', overflowY: 'auto', marginBottom: '14px' }}>
                    {courseList.length === 0 ? (
                      <div style={{ color: '#64748b', textAlign: 'center', padding: '20px 0', fontSize: '0.85rem' }}>선택된 문화유산 코스가 없습니다.</div>
                    ) : (
                      courseList.map((item, idx) => (
                        <div key={idx} style={{ display: 'flex', justify: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)', padding: '8px 12px', borderRadius: '8px', justifyContent: 'space-between' }}>
                          <span style={{ color: '#fff', fontSize: '0.85rem', fontWeight: 700 }}>{idx + 1}. {item.name}</span>
                          <button onClick={() => setCourseList(prev => prev.filter((_, i) => i !== idx))} style={{ background: 'none', border: 'none', color: '#f87171', fontSize: '1.05rem', cursor: 'pointer' }}>✕</button>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Transport & Duration Selector */}
                  <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <select value={courseTransport} onChange={(e) => setCourseTransport(e.target.value)} style={{ padding: '6px 10px', borderRadius: '6px', background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '0.85rem' }}>
                        <option value="승용차">🚗 승용차 (자가용)</option>
                        <option value="대중교통">🚌 대중교통 / 버스</option>
                        <option value="도보">🚶 도보 / 자전거</option>
                      </select>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>총 예상 소요시간</span>
                        <strong style={{ fontSize: '1.2rem', color: 'var(--accent-cyan)' }}>{courseTotalTimeText}</strong>
                      </div>
                    </div>
                  </div>
                </div>

                {/* AI 5선 추천지 Cards Deck */}
                {homeRecommendedCards.length > 0 && (
                  <div className="glass-card" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', justify: 'space-between', alignItems: 'center', marginBottom: '12px', justifyContent: 'space-between' }}>
                      <h4 style={{ fontSize: '1.05rem', color: 'var(--accent-cyan)', fontWeight: 800, margin: 0 }}>🤖 AI 추천 결과</h4>
                      <button onClick={copyRecommended5ToCourse} className="btn-primary" style={{ padding: '6px 12px', fontSize: '0.8rem', background: '#10b981', color: '#fff' }}>
                        + 전체 코스에 담기
                      </button>
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
                      {homeRecommendedCards.map((item, idx) => (
                        <div key={idx} style={{ display: 'flex', justify: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.02)', padding: '6px 10px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)', justifyContent: 'space-between' }}>
                          <span style={{ color: '#fff', fontSize: '0.82rem', fontWeight: 600 }}>{idx + 1}. {item.name}</span>
                          <button onClick={() => {
                            if (!courseList.some(c => c.name === item.name)) {
                              setCourseList(prev => [...prev, item]);
                              showToast(`🧭 '${item.name}' 코스에 담았습니다.`);
                            }
                          }} style={{ background: 'none', border: 'none', color: '#00f5d4', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 800 }}>+ 코스 추가</button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Guidebook storyboard trigger banner */}
            {courseList.length > 0 && (
              <div style={{ marginTop: '24px', padding: '18px 24px', background: 'linear-gradient(135deg, rgba(247,127,0,0.12), rgba(251,191,36,0.08))', border: '1px solid rgba(247, 127, 0, 0.4)', borderRadius: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--accent-amber)', margin: '0 0 4px 0' }}>📖 AI 맞춤 관광가이드북 만들기</h3>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-sub)', margin: 0 }}>선택하신 당일 코스를 기반으로 AI 에이전트들이 팁 카드 및 국/영문 가이드 가이드를 자동 제작합니다.</p>
                </div>
                <button onClick={generateGuidebookStoryboard} style={{ background: 'linear-gradient(135deg, #f77f00, #fcbf49)', color: '#0f172a', fontWeight: 900, border: 'none', borderRadius: '12px', padding: '12px 24px', fontSize: '0.92rem', cursor: 'pointer' }}>
                  {guidebookLoading ? '생성 중...' : '✨ 가이드북 만들기'}
                </button>
              </div>
            )}

            {/* Guidebook outputs block */}
            {(guidebookLoading || guidebookResult) && (
              <div ref={guidebookContainerRef} style={{ display: 'flex', flexDirection: 'column', gap: '18px', marginTop: '24px', borderTop: '1px solid var(--border-color)', paddingTop: '20px' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-amber)', margin: 0 }}>📖 엄마가 읽어주는 세종시 문화유산 동화책</h3>
                
                {/* 🎙️ Announcer Voice TTS Controller Dashboard */}
                {guidebookResult?.final_output && (
                  <div className="glass-card" style={{ display: 'flex', alignItems: 'center', justify: 'space-between', padding: '14px 20px', background: 'rgba(0, 245, 212, 0.04)', borderRadius: '12px', border: '1px solid rgba(0, 245, 212, 0.25)', marginBottom: '10px', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '1.4rem' }}>🎙️</span>
                      <div>
                        <strong style={{ color: '#fff', fontSize: '0.9rem', display: 'block' }}>여성 아나운서 구연동화 TTS</strong>
                        <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                          {isSpeaking ? (isPaused ? '⏸️ 일시정지 중...' : '🔊 따뜻하게 동화책을 읽어주는 중...') : '⏸️ 재생 준비 완료'}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {!isSpeaking ? (
                        <button onClick={startStorytellingTTS} className="btn-primary" style={{ padding: '8px 16px', fontSize: '0.82rem', background: '#00f5d4', color: '#0f172a', fontWeight: 800, border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
                          ▶️ 낭독 시작
                        </button>
                      ) : (
                        <>
                          {isPaused ? (
                            <button onClick={resumeStorytellingTTS} className="btn-secondary" style={{ padding: '8px 14px', fontSize: '0.82rem', cursor: 'pointer' }}>
                              ▶️ 재개
                            </button>
                          ) : (
                            <button onClick={pauseStorytellingTTS} className="btn-secondary" style={{ padding: '8px 14px', fontSize: '0.82rem', cursor: 'pointer' }}>
                              ⏸️ 일시정지
                            </button>
                          )}
                          <button onClick={stopStorytellingTTS} className="btn-secondary" style={{ padding: '8px 14px', fontSize: '0.82rem', background: 'rgba(239,68,68,0.2)', color: '#f87171', border: '1px solid rgba(239,68,68,0.4)', cursor: 'pointer' }}>
                            ⏹️ 정지
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Storyboard cards carousel */}
                <div style={{ display: 'flex', gap: '16px', overflowX: 'auto', paddingBottom: '10px' }}>
                  {guidebookResult?.storyboard_cards?.map((card, idx) => (
                    <div key={idx} className="glass-card" style={{ minWidth: '320px', maxWidth: '320px', padding: '14px', background: 'rgba(15,23,42,0.85)', border: '1.5px solid var(--accent-cyan)' }}>
                      <img src={card.image_url} style={{ width: '100%', borderRadius: '10px', marginBottom: '10px' }} alt={card.name} />
                      <h4 style={{ color: '#fff', fontSize: '1rem', fontWeight: 800, margin: '0 0 6px 0' }}>{card.name}</h4>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-sub)', marginBottom: '8px' }}>{card.address}</div>
                      <div style={{ background: 'rgba(0,245,212,0.06)', padding: '8px 12px', borderRadius: '8px', fontSize: '0.78rem', color: '#a7f3d0' }}>
                        💡 {card.guide_tip}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Guidebook articles */}
                {guidebookResult?.final_output && (
                  <div style={{ background: 'rgba(11,19,43,0.8)', border: '1px solid rgba(247,127,0,0.3)', borderRadius: '12px', padding: '22px', fontSize: '0.95rem', color: '#e2e8f0', whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                    {guidebookResult.final_output}
                  </div>
                )}
              </div>
            )}
          </>
        );
      case 'course':
        return (
          <>
            <div style={{ marginBottom: '16px' }}>
              <h2 className="page-title" style={{ fontSize: '1.4rem', color: '#00f5d4' }}>나만의 맞춤 코스 설계</h2>
              <p className="page-desc" style={{ fontSize: '0.85rem' }}>선택하신 세종시 문화유산을 지리 지도로 파악하고 총 소요시간 및 교통수단을 계산해 보세요.</p>
            </div>

            {/* Course route indicator bar */}
            <div style={{ marginBottom: '16px', padding: '14px', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.35)', borderRadius: '12px' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 800, color: '#34d399', marginBottom: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <span>AI 5선 맞춤 코스 경로 시각화</span>
                <button onClick={() => setShowLoadRoutesModal(true)} style={{ background: 'linear-gradient(135deg, #38bdf8, #00f5d4)', color: '#0f172a', fontWeight: 800, border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer' }}>
                  📂 코스 불러오기
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                {courseList.length === 0 ? (
                  <div style={{ color: 'var(--text-sub)', fontSize: '0.8rem', padding: '10px', width: '100%', textAlign: 'center', background: 'rgba(0,0,0,0.3)', borderRadius: '6px' }}>
                    코스에 담긴 유산이 없습니다. [추천] 또는 [검색] 메뉴에서 담아보세요.
                  </div>
                ) : (
                  courseList.map((c, i) => (
                    <React.Fragment key={i}>
                      <div style={{ background: 'rgba(0, 245, 212, 0.15)', border: '1px solid #00f5d4', borderRadius: '6px', padding: '4px 10px', fontSize: '0.8rem', fontWeight: 800, color: '#00f5d4' }}>
                        {i + 1}. {c.name}
                      </div>
                      {i < courseList.length - 1 && <span style={{ color: '#00f5d4' }}>➔</span>}
                    </React.Fragment>
                  ))
                )}
              </div>
            </div>

            {/* Map & Config forms */}
            <div className="grid-mobile-stack" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px', alignItems: 'flex-start' }}>
              <div className="glass-card gas-map-panel" style={{ padding: '12px', height: '360px' }}>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '8px' }}>🗺️ 세종시 코스 지리 마크맵</h3>
                <div style={{ height: '300px', position: 'relative' }}>
                  <MapComponent courseList={courseList} />
                </div>
              </div>

              <div className="gas-detail-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="glass-card" style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                    <h3 style={{ fontSize: '0.98rem', fontWeight: 700, color: '#fff', margin: 0 }}>🚩 코스 목록 ({courseList.length}개)</h3>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={() => setShowSaveCourseModal(true)} style={{ background: 'linear-gradient(135deg, #10b981, #00f5d4)', color: '#0f172a', fontWeight: 800, border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer' }}>
                        💾 저장
                      </button>
                      <button className="btn-secondary" onClick={() => setCourseList([])} style={{ padding: '3px 8px', fontSize: '0.75rem', borderColor: '#ef4444', color: '#ef4444', background: 'transparent' }}>
                        🗑️ 비우기
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', marginBottom: '14px' }}>
                    {courseList.length === 0 ? (
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center', padding: '10px' }}>목록이 비어 있습니다.</div>
                    ) : (
                      courseList.map((item, idx) => (
                        <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
                          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>{idx + 1}. {item.name}</span>
                          <button onClick={() => setCourseList(prev => prev.filter((_, i) => i !== idx))} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem' }}>✕ 삭제</button>
                        </div>
                      ))
                    )}
                  </div>

                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                    <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-sub)', marginBottom: '4px' }}>🚗 교통수단 선택</label>
                    <select value={courseTransport} onChange={(e) => setCourseTransport(e.target.value)} style={{ width: '100%', padding: '8px', background: '#151e36', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '6px', fontSize: '0.82rem', outline: 'none' }}>
                      <option value="승용차">🚗 승용차 (평균 시속 45km/h)</option>
                      <option value="대중교통">🚌 대중교통 (배차 대기시간 포함 계산)</option>
                      <option value="도보">🚶 도보 (천천히 걷기)</option>
                    </select>

                    <div style={{ marginTop: '12px', background: 'rgba(0,245,212,0.06)', border: '1px solid rgba(0,245,212,0.2)', padding: '10px 14px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                      <span style={{ fontSize: '0.82rem', color: 'var(--text-sub)' }}>⏱️ 예상 총 이동 시간:</span>
                      <strong style={{ fontSize: '1rem', color: 'var(--accent-cyan)' }}>약 {courseTotalDurationMin}분</strong>
                    </div>
                  </div>
                </div>

                {courseList.length > 0 && (
                  <button onClick={generateGuidebookStoryboard} style={{ width: '100%', background: 'linear-gradient(135deg, #f77f00, #fcbf49)', color: '#0f172a', fontWeight: 900, border: 'none', borderRadius: '12px', padding: '12px', fontSize: '0.92rem', cursor: 'pointer', textAlign: 'center' }}>
                    {guidebookLoading ? '⏳ 가이드북 제작 중...' : '✨ 이 코스로 AI 가이드북 만들기 (새 탭)'}
                  </button>
                )}
              </div>
            </div>
          </>
        );

      case 'guide':
        return (
          <>
            <div style={{ marginBottom: '16px' }}>
              <h2 className="page-title" style={{ fontSize: '1.4rem', color: 'var(--accent-amber)' }}>📖 AI 가이드북 스토리보드</h2>
              <p className="page-desc" style={{ fontSize: '0.85rem' }}>생성된 문화유산 스토리보드 카드 및 AI 에이전트들이 도출한 안내문을 확인해 보세요.</p>
            </div>

            {/* Guidebook outputs block */}
            {(!guidebookLoading && !guidebookResult) ? (
              <div style={{ textAlign: 'center', color: '#94a3b8', padding: '40px 20px', background: 'rgba(0,0,0,0.3)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.2)' }}>
                아직 생성된 가이드북이 없습니다. [코스 설계] 메뉴에서 코스를 설정하고 '가이드북 만들기'를 요청해보세요!
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-amber)', margin: 0 }}>📖 4대 에이전트 가이드 협업 결과</h3>
                  <span className="badge badge-era" style={{ background: 'rgba(247,127,0,0.15)', color: 'var(--accent-amber)' }}>
                    {guidebookLoading ? '⏳ 생성 중...' : '✅ 완료'}
                  </span>
                </div>

                <div style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '120px', overflowY: 'auto' }}>
                  {guidebookStepsLog.map((log, i) => (
                    <div key={i} style={{ color: log.includes('✅') ? '#34d399' : '#a0aec0' }}>{log}</div>
                  ))}
                </div>

                {guidebookResult && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Storyboard cards */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {guidebookResult.storyboard_cards?.map((card, idx) => (
                        <div key={idx} className="glass-card" style={{ padding: '14px', background: 'rgba(15,23,42,0.95)', border: '1px solid var(--accent-cyan)' }}>
                          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                            <div style={{ position: 'relative', width: '100%', height: '150px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--accent-cyan)' }}>
                              <img src={card.image_url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} alt={card.name} />
                              <span style={{ position: 'absolute', top: '6px', left: '6px', background: 'linear-gradient(135deg,#00f5d4,#7209b7)', color: '#fff', fontWeight: 900, width: '22px', height: '22px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem' }}>
                                {idx + 1}
                              </span>
                            </div>
                            <div style={{ flex: 1, minWidth: '240px' }}>
                              <h4 style={{ fontSize: '1rem', color: '#fff', fontWeight: 800, margin: '0 0 4px 0' }}>{idx + 1}. {card.name}</h4>
                              <div style={{ fontSize: '0.78rem', color: '#38bdf8', fontWeight: 700, marginBottom: '6px' }}>📍 주소: {card.address}</div>
                              <div style={{ background: 'rgba(0,245,212,0.06)', borderLeft: '3px solid var(--accent-cyan)', padding: '8px 10px', borderRadius: '6px', fontSize: '0.78rem', color: '#a7f3d0' }}>
                                💡 <strong>AI 팁:</strong> {card.guide_tip}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Guidebook articles */}
                    <div className="glass-card" style={{ padding: '16px' }}>
                      <h4 style={{ fontSize: '0.98rem', fontWeight: 800, color: 'var(--accent-cyan)', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '12px' }}>📖 통합 한국어 가이드 안내문 (안내 에이전트)</h4>
                      <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>
                        {guidebookResult.guidebook_ko_article || '안내문을 표시할 수 없습니다.'}
                      </p>
                    </div>

                    <div className="glass-card" style={{ padding: '16px' }}>
                      <h4 style={{ fontSize: '0.98rem', fontWeight: 800, color: 'var(--accent-blue)', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '12px' }}>📖 English Travel Guide (번역 에이전트)</h4>
                      <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>
                        {guidebookResult.guidebook_en_article || 'English guidebook is unavailable.'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        );

      case 'register':
        return (
          <>
            <div style={{ marginBottom: '24px' }}>
              <h1 className="page-title">🌱 고객이 찾은 문화유산 등록 서비스</h1>
              <p className="page-desc">세종시 구석구석 숨겨져 있는 미발굴 역사유산이나 가치 있는 생활 문화재를 제보해 주세요. 심사 후 AI 추천 서비스 풀에 등록됩니다.</p>
            </div>

            <div className="glass-card" style={{ padding: '28px', background: 'rgba(15, 23, 42, 0.85)', border: '1px solid var(--accent-cyan)', borderRadius: '18px' }}>
              <form onSubmit={submitCitizenReport} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>🏛️ 문화유산 이름</label>
                    <input
                      type="text"
                      placeholder="예: 조치원읍 미륵석불"
                      value={citFormName}
                      onChange={(e) => setCitFormName(e.target.value)}
                      required
                      style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: '0.95rem' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>📍 상세 위치 / 주소</label>
                    <input
                      type="text"
                      placeholder="예: 대한민국 조치원읍 봉산리"
                      value={citFormAddress}
                      onChange={(e) => setCitFormAddress(e.target.value)}
                      required
                      style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: '0.95rem' }}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>🌐 위도 (Latitude)</label>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="36.55"
                      value={citFormLat}
                      onChange={(e) => setCitFormLat(e.target.value)}
                      required
                      style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: '0.95rem' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>🌐 경도 (Longitude)</label>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="127.25"
                      value={citFormLng}
                      onChange={(e) => setCitFormLng(e.target.value)}
                      required
                      style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: '0.95rem' }}
                    />
                  </div>
                </div>

                <div>
                  <button type="button" onClick={acquireCurrentGPSLocation} style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px dashed #00f5d4', color: '#00f5d4', background: 'rgba(0,245,212,0.06)', fontWeight: 800, fontSize: '0.88rem', cursor: 'pointer' }}>
                    📡 내 현재 모바일 위치 좌표 수집
                  </button>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>📝 선정 이유 및 역사적 가치 설명</label>
                  <textarea
                    placeholder="이 문화유산의 가치와 추천하는 이유를 설명해 주세요..."
                    value={citFormReason}
                    onChange={(e) => setCitFormReason(e.target.value)}
                    required
                    rows={4}
                    style={{ width: '100%', padding: '12px 16px', borderRadius: '10px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: '0.95rem', resize: 'vertical' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>📸 문화유산 사진 첨부</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleCitizenPhotoSelect}
                    style={{ width: '100%', padding: '10px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', borderRadius: '8px' }}
                  />
                  {citFormPhotoPreview && (
                    <div style={{ marginTop: '14px', position: 'relative', borderRadius: '8px', overflow: 'hidden', border: '1.5px solid var(--accent-cyan)', maxHeight: '200px' }}>
                      <img src={citFormPhotoPreview} style={{ width: '100%', maxHeight: '100%', objectFit: 'cover' }} alt="미리보기" />
                    </div>
                  )}
                </div>

                <div style={{ marginTop: '10px' }}>
                  <button type="submit" className="btn-primary" style={{ width: '100%', padding: '14px', fontSize: '1.05rem', fontWeight: 900, background: 'linear-gradient(135deg, #00f5d4, #7209b7)', borderRadius: '12px', border: 'none', cursor: 'pointer' }}>
                    ⚡ 제보 등록 신청하기
                  </button>
                </div>

              </form>
            </div>
          </>
        );

      default:
        return <div>페이지를 찾을 수 없습니다.</div>;
    }
  };;

  return (
    <div className="mobile-frame-wrapper">
      <div className="mobile-device-chassis">
        {/* 📱 Mock Device Status Bar */}
        <div style={{ height: '24px', background: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 18px', fontSize: '0.72rem', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
          <span>23:59 📱</span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <span>📶</span>
            <span>🔋 100%</span>
          </div>
        </div>

        <div className="mobile-app-content">
          {/* Header Bar */}
          <header style={{ padding: '14px 16px', background: 'rgba(15,23,42,0.85)', borderBottom: '1px solid rgba(0,245,212,0.22)', display: 'flex', alignItems: 'center', gap: '10px', backdropFilter: 'blur(8px)' }}>
            <span style={{ fontSize: '1.4rem' }}>🇰🇷</span>
            <div>
              <h1 style={{ fontSize: '1.05rem', fontWeight: 900, margin: 0, background: 'linear-gradient(135deg, #00f5d4, #38bdf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                전국 스마트 문화유산
              </h1>
              <span style={{ fontSize: '0.62rem', color: '#64748b', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>National Heritage Platform</span>
            </div>
          </header>

          {/* Tab Content rendering */}
          <div style={{ padding: '16px', flex: 1 }}>
            {renderActiveTab()}
          </div>
        </div>

        {/* 📱 Mobile Fixed Bottom Navigation Bar */}
        <nav className="mobile-bottom-nav">
          <button onClick={() => setCurrentTab('home')} className={currentTab === 'home' ? 'active' : ''}>
            <span className="nav-icon">🏠</span>
            <span className="nav-label">추천 서비스</span>
          </button>
          <button onClick={() => setCurrentTab('register')} className={currentTab === 'register' ? 'active' : ''}>
            <span className="nav-icon">🌱</span>
            <span className="nav-label">유산 등록</span>
          </button>
        </nav>
      </div>
    </div>
  );;
}
