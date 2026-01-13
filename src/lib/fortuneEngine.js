import { createSeededRandom } from './seedRandom';
import { getWesternZodiac } from './zodiacWestern';
import { getChineseZodiac } from './zodiacChinese';

const toneLabel = {
  low: '주의',
  mid: '안정',
  high: '상승',
};

const pools = {
  total: {
    name: '총운',
    entries: {
      low: [
        {
          headline: '한 템포 쉬어가도 괜찮아요',
          detail: '바쁘게 달려온 만큼 잠시 숨을 고르며 주변을 돌아볼 때입니다.',
          tip: '가벼운 스트레칭과 산책으로 리듬을 맞춰보세요.',
          caution: '중요 결정을 서두르지 마세요.',
        },
        {
          headline: '디테일 점검의 날',
          detail: '작은 실수가 큰 파급력을 가질 수 있는 날입니다. 계획을 다시 점검하세요.',
          tip: '체크리스트를 작성해 하나씩 지워나가세요.',
          caution: '피곤할 때 무리해서 야근하지 마세요.',
        },
      ],
      mid: [
        {
          headline: '균형감이 돋보이는 하루',
          detail: '크고 작은 일들이 무난하게 흘러갑니다. 루틴을 유지하면 좋은 흐름이 이어집니다.',
          tip: '정리정돈으로 마음의 여백을 확보하세요.',
          caution: '주변의 소소한 부탁을 무심히 넘기지 마세요.',
        },
        {
          headline: '안정된 파도 위를 항해 중',
          detail: '예상한 범위 안에서 일들이 처리됩니다. 조금의 여유를 누려보세요.',
          tip: '마음에 드는 음악을 틀어두고 집중하세요.',
          caution: '과신으로 체크를 건너뛰지 마세요.',
        },
      ],
      high: [
        {
          headline: '빛나는 시너지의 순간',
          detail: '여러 요소가 맞물려 좋은 결과를 끌어낼 타이밍입니다. 자신감 있게 움직이세요.',
          tip: '새로운 제안이나 협업을 먼저 제시해보세요.',
          caution: '성과를 나누는 방식에서 공정함을 잊지 마세요.',
        },
        {
          headline: '행운의 흐름을 타고 있어요',
          detail: '평소보다 기회가 자주 눈에 들어옵니다. 과감한 선택이 득이 될 수 있습니다.',
          tip: '과감히 도전하고 결과를 기록해두세요.',
          caution: '과욕으로 휴식을 잊지 마세요.',
        },
      ],
    },
  },
  love: {
    name: '연애운',
    entries: {
      low: [
        {
          headline: '감정의 온도 조절 필요',
          detail: '말투가 조금만 날카로워져도 오해가 생길 수 있어요.',
          tip: '메시지를 보내기 전 한 번 더 읽어보세요.',
          caution: '상대의 말을 끊지 마세요.',
        },
        {
          headline: '거리두기가 도움이 되는 날',
          detail: '혼자만의 시간이 관계에 숨을 틔워줄 수 있습니다.',
          tip: '짧은 산책이나 카페 타임으로 마음을 정돈하세요.',
          caution: '예민한 주제로 대화를 길게 이어가지 마세요.',
        },
      ],
      mid: [
        {
          headline: '잔잔한 파동이 이어집니다',
          detail: '크게 설레지는 않지만 편안함이 지속됩니다.',
          tip: '상대가 좋아하는 소소한 배려를 하나 실천해보세요.',
          caution: '무심코 지나치지 않도록 감사를 표현하세요.',
        },
        {
          headline: '익숙함 속 새로운 포인트',
          detail: '오랜 패턴에서 벗어나 작은 이벤트를 준비하면 좋은 반응이 옵니다.',
          tip: '평소와 다른 길을 함께 걸어보세요.',
          caution: '약속 시간을 자주 변경하지 마세요.',
        },
      ],
      high: [
        {
          headline: '따뜻한 시선이 오가는 날',
          detail: '말하지 않아도 통하는 순간이 늘어납니다. 감정 표현을 아끼지 마세요.',
          tip: '짧은 손편지나 음성 메시지를 남겨보세요.',
          caution: '상대의 속도를 존중하세요.',
        },
        {
          headline: '끌림이 선명하게 느껴집니다',
          detail: '소개팅, 데이트, 고백에 좋은 타이밍. 솔직함이 매력으로 작용합니다.',
          tip: '시선을 맞추고 미소로 시작하세요.',
          caution: '말보다는 행동으로 확신을 보여주세요.',
        },
      ],
    },
  },
  study: {
    name: '학업운',
    entries: {
      low: [
        {
          headline: '집중도가 분산되기 쉬운 날',
          detail: '외부 자극이 많아 학습 흐름이 끊길 수 있습니다.',
          tip: '25분 집중, 5분 휴식의 짧은 루틴을 사용해보세요.',
          caution: '여러 과목을 한꺼번에 펼쳐두지 마세요.',
        },
        {
          headline: '기초를 다시 다질 타이밍',
          detail: '속도가 나지 않는다면 기본 개념 복습이 도움이 됩니다.',
          tip: '핵심 공식이나 정의를 써보며 암기하세요.',
          caution: '새로운 문제집을 지금 바로 열지 마세요.',
        },
      ],
      mid: [
        {
          headline: '루틴대로만 가도 충분해요',
          detail: '평소 계획을 꾸준히 지키면 안정적인 성과가 납니다.',
          tip: '완료한 분량을 눈에 보이게 체크하세요.',
          caution: '휴식 시간을 과하게 줄이지 마세요.',
        },
        {
          headline: '학습 몰입 시간이 찾아옵니다',
          detail: '한 번 집중이 잡히면 생각보다 많은 진도를 나갈 수 있어요.',
          tip: '방해 요소를 치우고 타이머를 설정하세요.',
          caution: '스마트폰 확인을 30분마다로 제한하세요.',
        },
      ],
      high: [
        {
          headline: '지식이 연결되는 쾌감',
          detail: '배운 내용이 유기적으로 이어지며 이해도가 높아집니다.',
          tip: '새로운 아이디어를 메모하고 정리하세요.',
          caution: '완벽주의로 진도를 막지 마세요.',
        },
        {
          headline: '결과로 이어질 날',
          detail: '모의고사나 발표에서 좋은 피드백을 기대할 수 있습니다.',
          tip: '주요 예상 문제를 한 번 더 정리하세요.',
          caution: '컨디션 조절을 위해 수면을 충분히 확보하세요.',
        },
      ],
    },
  },
  money: {
    name: '금전운',
    entries: {
      low: [
        {
          headline: '지출이 늘어날 수 있어요',
          detail: '충동 구매나 예기치 못한 비용이 생길 가능성이 있습니다.',
          tip: '오늘의 한도 금액을 미리 정해두세요.',
          caution: '신용카드 무이자 행사에 지나치게 기대지 마세요.',
        },
        {
          headline: '수익보다 보존이 우선',
          detail: '큰 투자 결정은 하루 미루고, 현금 흐름을 점검하세요.',
          tip: '지출 카테고리를 나누어 기록하세요.',
          caution: '친구의 투자 제안을 바로 수락하지 마세요.',
        },
      ],
      mid: [
        {
          headline: '흐름을 유지하는 날',
          detail: '예상한 범위 내에서 들어오고 나가는 돈이 균형을 이룹니다.',
          tip: '자동이체 내역을 한번 확인하세요.',
          caution: '감정 소비를 피하려면 간식 예산을 정하세요.',
        },
        {
          headline: '실용적 선택이 돋보입니다',
          detail: '필요한 곳에 알맞게 쓰면 가성비가 살아납니다.',
          tip: '리뷰를 꼼꼼히 보고 구매하세요.',
          caution: '불필요한 구독을 그대로 두지 마세요.',
        },
      ],
      high: [
        {
          headline: '이익을 끌어당기는 기운',
          detail: '협상이나 판매, 보너스 협의에 좋은 타이밍입니다.',
          tip: '가격 비교 후 자신 있게 제안하세요.',
          caution: '큰 금액은 계약서로 남기세요.',
        },
        {
          headline: '수확의 손길',
          detail: '그동안의 노력에 대한 보상이 기대됩니다. 작은 복권도 운이 따릅니다.',
          tip: '미뤄둔 환급, 포인트 전환을 챙기세요.',
          caution: '우연한 횡재에 모든 계획을 걸지 마세요.',
        },
      ],
    },
  },
  health: {
    name: '건강운',
    entries: {
      low: [
        {
          headline: '체력 관리가 필요한 날',
          detail: '피로가 쌓이기 쉬우니 몸의 신호에 귀 기울이세요.',
          tip: '따뜻한 차와 가벼운 스트레칭으로 순환을 돕세요.',
          caution: '무리한 운동 강도를 피하세요.',
        },
        {
          headline: '면역력 체크',
          detail: '컨디션이 살짝 떨어질 수 있습니다. 꾸준한 수분 섭취가 중요해요.',
          tip: '비타민과 수분을 챙기고 휴식 알람을 설정하세요.',
          caution: '밤늦은 간식은 오늘만큼은 참아보세요.',
        },
      ],
      mid: [
        {
          headline: '안정된 컨디션',
          detail: '평소 루틴을 유지하면 무난하게 지나갑니다.',
          tip: '짧은 명상으로 집중력을 끌어올리세요.',
          caution: '자세를 자주 바꿔 목, 어깨를 풀어주세요.',
        },
        {
          headline: '회복탄력성이 돋보여요',
          detail: '가벼운 운동과 균형 잡힌 식사가 컨디션을 지켜줍니다.',
          tip: '물병을 눈에 띄는 곳에 두고 자주 마시세요.',
          caution: '카페인 섭취량을 조절하세요.',
        },
      ],
      high: [
        {
          headline: '에너지가 충만한 하루',
          detail: '몸이 가뿐하게 움직여 활동량을 늘리기 좋습니다.',
          tip: '평소보다 한 단계 높은 운동을 시도해보세요.',
          caution: '준비운동과 마무리 스트레칭을 잊지 마세요.',
        },
        {
          headline: '몸과 마음이 가볍습니다',
          detail: '수면과 식사 리듬이 잘 맞아 활력을 느낄 수 있습니다.',
          tip: '햇빛을 10분만이라도 쬐어보세요.',
          caution: '과도한 스케줄로 에너지를 한 번에 소진하지 마세요.',
        },
      ],
    },
  },
};

const colors = [
  { name: '네온 바이올렛', value: '#8b7bff' },
  { name: '코발트 블루', value: '#5aa7ff' },
  { name: '코스믹 핑크', value: '#ff7bd8' },
  { name: '에메랄드 그린', value: '#6de5ae' },
  { name: '샌드 골드', value: '#ffd37b' },
  { name: '라피스 네이비', value: '#1f2b6f' },
];

const luckyItems = ['별 모양 액세서리', '은은한 향의 향초', '블루 펜', '둥근 돌', '메모장', '따뜻한 머그컵', '행운의 동전', '카드 지갑'];
const luckyKeywords = ['몰입', '정리', '대화', '도전', '휴식', '신뢰', '순발력', '유연성'];

const pickTone = (score) => {
  if (score < 40) return 'low';
  if (score < 70) return 'mid';
  return 'high';
};

const createFortuneItem = (key, rng, scoreRange = null) => {
  const score = scoreRange ? rng.nextInt(scoreRange.min, scoreRange.max) : rng.nextInt(25, 98);
  const tone = pickTone(score);
  const bucket = pools[key];
  const choice = rng.pick(bucket.entries[tone]);
  return {
    key,
    name: bucket.name,
    score,
    tone,
    toneLabel: toneLabel[tone],
    ...choice,
  };
};

const getOverallRangeByRank = (rank) => {
  if (rank >= 1 && rank <= 3) return { min: 85, max: 100 };
  if (rank >= 4 && rank <= 6) return { min: 65, max: 85 };
  if (rank >= 7 && rank <= 9) return { min: 45, max: 65 };
  if (rank >= 10 && rank <= 12) return { min: 20, max: 45 };
  return null;
};

export const generateFortune = (birthdate, todayKst, rank = null) => {
  const seed = `${todayKst}|${birthdate}|ohahasa-v1`;
  const rng = createSeededRandom(seed);
  const totalRange = getOverallRangeByRank(rank);
  const fortunes = ['total', 'love', 'study', 'money', 'health'].map((key) =>
    createFortuneItem(key, rng, key === 'total' ? totalRange : null)
  );

  const colorPick = rng.pick(colors);

  const lucky = {
    color: colorPick.value,
    colorName: colorPick.name,
    number: rng.nextInt(1, 9),
    item: rng.pick(luckyItems),
    keyword: rng.pick(luckyKeywords),
  };

  return {
    date: todayKst,
    birthdate,
    westernZodiac: getWesternZodiac(birthdate),
    chineseZodiac: getChineseZodiac(birthdate),
    fortunes,
    lucky,
  };
};
