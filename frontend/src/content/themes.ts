// Chapter titles for each mistake theme (fixed copy — the backend sends the theme key and name).
// Keys are the Lichess puzzle-theme names produced by the tagger (docs/PLAN.md §4.3).
const CHAPTER_TITLES: Record<string, string> = {
  hangingPiece: 'You leave pieces undefended',
  fork: 'You walk into forks',
  pin: 'You walk into pins',
  skewer: 'You walk into skewers',
  discoveredAttack: 'You miss discovered attacks',
  backRankMate: 'Your back rank is weak',
  trappedPiece: 'Your pieces get trapped',
  exposedKing: 'Your king gets exposed',
  advancedPawn: 'You let passed pawns run',
  quietMove: 'You miss quiet killer moves',
  defensiveMove: 'You miss the only defence',
}

export function chapterTitle(theme: string, name: string): string {
  return CHAPTER_TITLES[theme] ?? name
}

export const ROMAN = ['I.', 'II.', 'III.', 'IV.', 'V.']
