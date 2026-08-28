import os
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load from C:\Anti-project\.env
load_dotenv(r"C:\Anti-project\.env")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Supabase credentials missing in C:\\Anti-project\\.env!")
    exit(1)

# Base headers for Supabase REST API
headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
    "Content-Type": "application/json"
}

# The 34 cultural heritages (2 per 17 regions) with pre-verified coords & details
HERITAGE_LIST = [
    # 1. 서울
    {
        "region": "서울특별시",
        "name": "경복궁",
        "address": "서울특별시 종로구 사직로 161",
        "latitude": 37.5796,
        "longitude": 126.9770,
        "fallback_desc": "조선 왕조의 법궁으로, 1395년에 창건된 조선의 대표적인 궁궐입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1547826039-bfc35e0f1ea8?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "서울특별시",
        "name": "창덕궁",
        "address": "서울특별시 종로구 율곡로 99",
        "latitude": 37.5794,
        "longitude": 126.9910,
        "fallback_desc": "자연과의 조화가 돋보이는 궁궐로, 유네스코 세계문화유산으로 지정되어 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1617053531393-27cfbe45c613?auto=format&fit=crop&w=800&q=80"
    },
    # 2. 부산
    {
        "region": "부산광역시",
        "name": "범어사",
        "address": "부산광역시 금정구 범어사로 250",
        "latitude": 35.2838,
        "longitude": 129.0686,
        "fallback_desc": "신라 문무왕 때 의상대사가 창건한 영남 3대 사찰 중 하나입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1620802613528-ee6115d7f2ec?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "부산광역시",
        "name": "부산 충렬사",
        "address": "부산광역시 동래구 충렬대로 347",
        "latitude": 35.2013,
        "longitude": 129.0910,
        "fallback_desc": "임진왜란 때 왜적과 싸우다 순절한 동래부사 송상현 등 순국선열들을 모신 사당입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=800&q=80"
    },
    # 3. 대구
    {
        "region": "대구광역시",
        "name": "동화사",
        "address": "대구광역시 동구 동화사1길 1",
        "latitude": 35.9863,
        "longitude": 128.7180,
        "fallback_desc": "팔공산에 위치한 사찰로, 통일약사여래대불이 유명한 대구의 대표 사찰입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1608976451631-b850ded0e2d3?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "대구광역시",
        "name": "달성토성",
        "address": "대구광역시 중구 달성공원로 35",
        "latitude": 35.8726,
        "longitude": 128.5786,
        "fallback_desc": "삼국시대에 축조된 평지 토성으로, 오늘날 달성공원으로 시민들에게 사랑받고 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1508193638397-1c4234db14d8?auto=format&fit=crop&w=800&q=80"
    },
    # 4. 인천
    {
        "region": "인천광역시",
        "name": "전등사",
        "address": "인천광역시 강화군 길상면 전등사로 37-41",
        "latitude": 37.6322,
        "longitude": 126.4844,
        "fallback_desc": "강화도에 위치한 삼국시대 고찰로, 대웅보전의 나부상 조각 등 많은 보물을 간직하고 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1616788494707-ec28f08d05a1?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "인천광역시",
        "name": "강화 고인돌 유적",
        "address": "인천광역시 강화군 하점면 고인돌로 17",
        "latitude": 37.7802,
        "longitude": 126.4402,
        "fallback_desc": "유네스코 세계문화유산으로 지정된 청동기시대의 대표적인 지석묘 군락지입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1601004890684-d8cbf643f5f2?auto=format&fit=crop&w=800&q=80"
    },
    # 5. 광주
    {
        "region": "광주광역시",
        "name": "증심사",
        "address": "광주광역시 동구 증심사길 150",
        "latitude": 35.1226,
        "longitude": 126.9745,
        "fallback_desc": "무등산 기슭에 자리 잡은 고찰로, 철조비로자나불좌상 등 다양한 문화유산이 보존되어 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1528164344705-47542687000d?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "광주광역시",
        "name": "환벽당",
        "address": "광주광역시 북구 충효동 387",
        "latitude": 35.1873,
        "longitude": 127.0006,
        "fallback_desc": "사촌 김윤제가 건립하여 후학들을 가르치던 정자로, 무등산 원림의 아름다움을 잘 보여줍니다.",
        "fallback_img": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80"
    },
    # 6. 대전
    {
        "region": "대전광역시",
        "name": "동춘당",
        "address": "대전광역시 대덕구 동춘당로 80",
        "latitude": 36.3630,
        "longitude": 127.4418,
        "fallback_desc": "조선 중기의 학자 송준길 선생이 지은 별당 건물로, 고즈넉한 한국 전통 건축의 미를 보여줍니다.",
        "fallback_img": "https://images.unsplash.com/photo-1578002573559-689b0bb41481?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "대전광역시",
        "name": "계족산성",
        "address": "대전광역시 대덕구 장동 산85",
        "latitude": 36.3882,
        "longitude": 127.4580,
        "fallback_desc": "백제 시대에 돌로 쌓아 만든 산성으로, 대전 시내와 대청호의 풍경을 한눈에 볼 수 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1518391846015-55a9cc003b25?auto=format&fit=crop&w=800&q=80"
    },
    # 7. 울산
    {
        "region": "울산광역시",
        "name": "울주 대곡리 반구대 암각화",
        "address": "울산광역시 울주군 언양읍 반구대안길 285",
        "latitude": 35.6027,
        "longitude": 129.1784,
        "fallback_desc": "선사시대 사람들이 바위에 고래, 호랑이, 사슴 등 다양한 그림을 새겨놓은 국보 유적입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "울산광역시",
        "name": "울주 천전리 각석",
        "address": "울산광역시 울주군 두동면 천전리 산210-2",
        "latitude": 35.6133,
        "longitude": 129.1804,
        "fallback_desc": "선사시대의 기하학적 문양과 신라 시대의 인물상, 글자가 함께 새겨진 바위 유적입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1473163928189-364b2c4e1135?auto=format&fit=crop&w=800&q=80"
    },
    # 8. 세종
    {
        "region": "세종특별자치시",
        "name": "비암사",
        "address": "세종특별자치시 전의면 비암사길 137",
        "latitude": 36.6083,
        "longitude": 127.2140,
        "fallback_desc": "삼국시대 창건된 것으로 추정되는 고찰로, 계유명전씨아미타불비상 등 귀중한 비상들이 발견된 곳입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1598902108854-10e335adac99?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "세종특별자치시",
        "name": "임난수 장군 독락정",
        "address": "세종특별자치시 나성동 242",
        "latitude": 36.4851,
        "longitude": 127.2721,
        "fallback_desc": "고려 말의 무신 임난수 장군을 기리기 위해 세운 정자로, 금강 변의 경치를 감상하기 좋습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
    },
    # 9. 경기
    {
        "region": "경기도",
        "name": "수원 화성",
        "address": "경기도 수원시 팔달구 정조로 910",
        "latitude": 37.2882,
        "longitude": 127.0169,
        "fallback_desc": "정조 대왕이 효심과 왕권 강화를 위해 축성한 계획도시 성곽으로, 유네스코 세계문화유산입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1590254558506-c8ad5fb9d089?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "경기도",
        "name": "남한산성",
        "address": "경기도 광주시 남한산성면 남한산성로 731",
        "latitude": 37.4795,
        "longitude": 127.1843,
        "fallback_desc": "병자호란의 아픈 역사가 깃든 산성이자 군사 요새로, 유네스코 세계문화유산으로 등재되었습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1501854140801-50d01698950b?auto=format&fit=crop&w=800&q=80"
    },
    # 10. 강원
    {
        "region": "강원특별자치도",
        "name": "강릉 오죽헌",
        "address": "강원특별자치도 강릉시 율곡로 3139번길 24",
        "latitude": 37.7792,
        "longitude": 128.8795,
        "fallback_desc": "신사임당과 율곡 이이가 태어난 집으로, 우리나라 주택 건축 중 가장 오래된 별당 건물 중 하나입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "강원특별자치도",
        "name": "평창 월정사",
        "address": "강원특별자치도 평창군 진부면 오대산로 374-8",
        "latitude": 37.7317,
        "longitude": 128.5905,
        "fallback_desc": "오대산의 웅장한 자연 속에 자리 잡은 사찰로, 팔각구층석탑과 전나무 숲길로 널리 알려져 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80"
    },
    # 11. 충북
    {
        "region": "충청북도",
        "name": "보은 법주사",
        "address": "충청북도 보은군 속리산면 법주사로 405",
        "latitude": 36.5422,
        "longitude": 127.8347,
        "fallback_desc": "속리산에 위치한 천년고찰로, 우리나라 유일의 목탑인 팔상전과 거대한 금동미륵대불이 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1542224566-6e85f2e6772f?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "충청북도",
        "name": "충주 탑평리 칠층석탑",
        "address": "충청북도 충주시 중앙탑면 탑정안길 6",
        "latitude": 37.0165,
        "longitude": 127.8631,
        "fallback_desc": "통일신라 시대 나라의 중앙에 위치한다고 하여 '중앙탑'으로도 불리는 국보 석탑입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?auto=format&fit=crop&w=800&q=80"
    },
    # 12. 충남
    {
        "region": "충청남도",
        "name": "공주 무령왕릉",
        "address": "충청남도 공주시 왕릉로 37",
        "latitude": 36.4600,
        "longitude": 127.1189,
        "fallback_desc": "백제 25대 무령왕과 왕비의 무덤으로, 도굴되지 않은 상태로 발견되어 백제 미술의 정수를 보여줍니다.",
        "fallback_img": "https://images.unsplash.com/photo-1605538032432-a9f0c8d9baac?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "충청남도",
        "name": "공주 공산성",
        "address": "충청남도 공주시 웅진로 280",
        "latitude": 36.4632,
        "longitude": 127.1264,
        "fallback_desc": "백제의 두 번째 수도인 웅진을 방어하기 위해 쌓은 성곽으로, 아름다운 금강의 전경을 볼 수 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=800&q=80"
    },
    # 13. 전북
    {
        "region": "전북특별자치도",
        "name": "전주 전동성당",
        "address": "전북특별자치도 전주시 완산구 태조로 51",
        "latitude": 35.8132,
        "longitude": 127.1493,
        "fallback_desc": "호남 지역 최초의 로마네스크 양식 성당으로, 아름다운 붉은 벽돌 건축이 한옥마을과 어우러집니다.",
        "fallback_img": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "전북특별자치도",
        "name": "익산 미륵사지",
        "address": "전북특별자치도 익산시 금마면 기양리 97",
        "latitude": 36.0125,
        "longitude": 126.9774,
        "fallback_desc": "동양 최대 규모의 백제 사찰 터로, 국보인 익산 미륵사지 석탑이 유명한 세계문화유산입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80"
    },
    # 14. 전남
    {
        "region": "전라남도",
        "name": "순천 송광사",
        "address": "전라남도 순천시 송광면 송광사안길 100",
        "latitude": 34.9961,
        "longitude": 127.2721,
        "fallback_desc": "한국의 삼보사찰 중 승보사찰에 해당하며, 수많은 고승들을 배출한 명찰입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1528164344705-47542687000d?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "전라남도",
        "name": "구례 화엄사",
        "address": "전라남도 구례군 마산면 화엄사로 539",
        "latitude": 35.2572,
        "longitude": 127.4988,
        "fallback_desc": "지리산 자락에 자리 잡은 고찰로, 각황전과 삼층석탑 등 웅장하고 아름다운 국보 문화재가 많습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80"
    },
    # 15. 경북
    {
        "region": "경상북도",
        "name": "경주 불국사",
        "address": "경상북도 경주시 불국로 385",
        "latitude": 35.7900,
        "longitude": 129.3323,
        "fallback_desc": "토함산 기슭의 신라 불교 예술의 결정체로, 다보탑과 석가탑 등 국보 문화재의 보고입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1620802613528-ee6115d7f2ec?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "경상북도",
        "name": "경주 석굴암",
        "address": "경상북도 경주시 불국로 873-243",
        "latitude": 35.7949,
        "longitude": 129.3491,
        "fallback_desc": "화강암을 돔형으로 정교하게 조각하여 만든 신라 인공 석굴 사원으로, 세계적인 걸작입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1542224566-6e85f2e6772f?auto=format&fit=crop&w=800&q=80"
    },
    # 16. 경남
    {
        "region": "경상남도",
        "name": "합천 해인사",
        "address": "경상남도 합천군 가야면 해인사길 122",
        "latitude": 35.7997,
        "longitude": 128.0975,
        "fallback_desc": "가야산에 위치한 법보사찰로, 고려 대장경판을 보관하고 있는 장경판전(세계유산)이 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1598902108854-10e335adac99?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "경상남도",
        "name": "양산 통도사",
        "address": "경상남도 양산시 하북면 통도사로 108",
        "latitude": 35.4839,
        "longitude": 129.0638,
        "fallback_desc": "우리나라 삼보사찰 중 불보사찰로, 대웅전 뒤편 사리탑에 부처님의 진신사리를 모시고 있습니다.",
        "fallback_img": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
    },
    # 17. 제주
    {
        "region": "제주특별자치도",
        "name": "제주 목관아",
        "address": "제주특별자치도 제주시 관덕로 25",
        "latitude": 33.5135,
        "longitude": 126.5222,
        "fallback_desc": "조선시대 제주 행정의 중심지였던 관아지 유적으로, 제주의 오랜 역사적 중심지입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1501854140801-50d01698950b?auto=format&fit=crop&w=800&q=80"
    },
    {
        "region": "제주특별자치도",
        "name": "제주 삼성혈",
        "address": "제주특별자치도 제주시 삼성로 22",
        "latitude": 33.5064,
        "longitude": 126.5312,
        "fallback_desc": "제주도의 시조인 고을나, 양을나, 부을나 세 신인이 지상에서 솟아났다는 전설의 세 구멍이 있는 사적입니다.",
        "fallback_img": "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=800&q=80"
    }
]

def fetch_naver_terms_info(name):
    """Scrapes description and thumbnail image from Naver Terms Search (Encyclopedia)"""
    url = f"https://terms.naver.com/search.naver?query={urllib.parse.quote(name)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client() as client:
            r = client.get(url, headers=headers, follow_redirects=True, timeout=6.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                first_item = soup.select_one("ul.content_list > li")
                if first_item:
                    # Extract description
                    desc_elem = first_item.select_one(".info_area .desc")
                    desc = desc_elem.get_text().strip() if desc_elem else ""
                    
                    # Extract image data-src
                    img_elem = first_item.select_one(".thumb_area img")
                    img_url = ""
                    if img_elem:
                        raw_src = img_elem.get("data-src") or img_elem.get("src")
                        if raw_src and "pstatic.net" in raw_src:
                            img_url = raw_src
                    return desc, img_url
    except Exception as e:
        print(f"Error fetching Naver Terms for {name}: {e}")
    return "", ""

def main():
    print(f"Starting to insert/update {len(HERITAGE_LIST)} cultural heritages to Supabase...")
    
    with httpx.Client() as client:
        success_count = 0
        for i, item in enumerate(HERITAGE_LIST):
            name = item["name"]
            address = item["address"]
            lat = item["latitude"]
            lng = item["longitude"]
            
            print(f"\n[{i+1}/{len(HERITAGE_LIST)}] Processing '{name}' ({item['region']})...")
            
            # 1. Fetch Naver Encyclopedia info
            naver_desc, naver_img = fetch_naver_terms_info(name)
            
            # Determine description
            description = naver_desc if naver_desc else item["fallback_desc"]
            # Clean up double spaces or brackets if needed
            description = description.replace("\xa0", " ").strip()
            
            # Determine image URL
            image_url = naver_img if naver_img else item["fallback_img"]
            
            print(f"  - Scraped Naver Desc: {description[:60]}...")
            print(f"  - Image URL: {image_url[:60]}...")
            
            # Prepare payload matching supabase columns
            payload = {
                "name": name,
                "address": address,
                "description": description,
                "reason": description,  # compatibility column if any
                "latitude": lat,
                "longitude": lng,
                "image_url": image_url,
                "photo_url": image_url,  # compatibility column if any
                "user_id": "system@sejong.go.kr",
                "status": "승인",
                "recommend_count": 1,
                "heart": 0
            }
            
            # 2. Check duplicate in database
            check_url = f"{supabase_url}/rest/v1/citizen_recommendations?name=eq.{urllib.parse.quote(name)}&select=id"
            try:
                res_check = client.get(check_url, headers=headers)
                spot_id = None
                if res_check.status_code == 200:
                    records = res_check.json()
                    if len(records) > 0:
                        spot_id = records[0]["id"]
                
                if spot_id:
                    # Update
                    patch_url = f"{supabase_url}/rest/v1/citizen_recommendations?id=eq.{spot_id}"
                    res_patch = client.patch(patch_url, headers=headers, json=payload)
                    if res_patch.status_code in [200, 204]:
                        print(f"  => Successfully UPDATED in database (ID: {spot_id})")
                        success_count += 1
                    else:
                        print(f"  => Failed to update: {res_patch.status_code} - {res_patch.text}")
                else:
                    # Insert
                    insert_url = f"{supabase_url}/rest/v1/citizen_recommendations"
                    res_insert = client.post(insert_url, headers=headers, json=payload)
                    if res_insert.status_code in [200, 201, 204]:
                        print("  => Successfully INSERTED new record into database")
                        success_count += 1
                    else:
                        print(f"  => Failed to insert: {res_insert.status_code} - {res_insert.text}")
                        
            except Exception as e:
                print(f"  => Connection error: {e}")
                
        print(f"\nCompleted processing. Successfully updated/inserted {success_count}/{len(HERITAGE_LIST)} records.")

if __name__ == "__main__":
    main()
