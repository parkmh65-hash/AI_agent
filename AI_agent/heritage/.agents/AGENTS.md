# Project-Scoped Rules

## Git & Cloud Run Integration Constraints
* **Server Code Push Rule**: `Server` 폴더 내의 백엔드 소스 코드에 어떠한 수정사항이라도 발생하면, 통합 테스트 검증을 완료한 후 즉시 해당 변경사항을 스테이징 및 커밋하여 깃허브(GitHub) 원격 레포지토리 `main` 브랜치에 자동으로 업로드(`git push`)해야 합니다.
* **Google Cloud Run Deployment Rule**: 깃허브에 백엔드 소스 코드 업로드가 완료되면, 즉시 아래의 GCP 배포 명령을 로컬 터미널에서 실행하여 구글 클라우드 런 실환경에 동시 배포를 진행하고 완료 여부를 보고해야 합니다:
  `gcloud run deploy heritage-react --source ver_02/Server --region us-central1 --allow-unauthenticated`
