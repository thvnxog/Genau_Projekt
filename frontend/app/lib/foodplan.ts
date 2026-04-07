// Zentrale Domain-Typen und UI-Helfer für den Foodplan-Flow.
// Diese Datei bündelt gemeinsame Modelle, Labels und kleine Utility-Funktionen.

// Ergebnis je Regel im Report.
export type SchoolLevel = 'P' | 'S';

export type RuleResult = {
  id: string;
  label: string;
  applies: boolean;
  passed: boolean;
  target?: { count_by?: string; value?: string | string[] };
  expected?: string;
  actual?: number;
  notes?: string;
};

export type GramHint = {
  id: string;
  label: string;
  target?: { count_by?: string; value?: string | string[] };
  current_grams: number;
  target_grams: number;
  missing_grams: number;
  status: 'ok' | 'needs_more';
};

export type ReportSingle = {
  summary: { score: number; passed_rules: number; applicable_rules: number };
  gram_hints?: GramHint[];
  rules: RuleResult[];
};

export type ReportDual = {
  mode: 'dual';
  school_level?: SchoolLevel;
  calculation?: {
    mode: 'estimated';
    school_level?: SchoolLevel | null;
    school_level_label?: string;
    days_considered?: number;
    note?: string;
  };
  mixed: ReportSingle;
  ovo_lacto_vegetarian: ReportSingle;
};

export type WeeklyReportDual = {
  week_index: number;
  week_label: string;
  mixed: ReportSingle;
  ovo_lacto_vegetarian: ReportSingle;
};

export type ReportMonthlyDual = {
  mode: 'monthly_dual';
  school_level?: SchoolLevel;
  calculation?: {
    mode: 'estimated';
    school_level?: SchoolLevel | null;
    school_level_label?: string;
    days_considered?: number;
    note?: string;
  };
  monthly_summary: {
    weeks: number;
    mixed: ReportSingle['summary'];
    ovo_lacto_vegetarian: ReportSingle['summary'];
  };
  weekly_reports: WeeklyReportDual[];
};

export type AnalyzeResponse = ReportDual | ReportMonthlyDual;

// Strukturen für den editierbaren Plan im Selbstcheck.
export type PlanItem = {
  raw_text?: string;
  links?: { food_group?: string | null };
  tags?: string[];
  food_groups?: string[];
};

export type PlanMenu = {
  menu_type?: string;
  items?: PlanItem[];
};

export type PlanDay = {
  weekday?: string;
  week_index?: number;
  week_label?: string;
  menus?: PlanMenu[];
};

export type PlanDoc = {
  schema_version?: string;
  days?: PlanDay[];
};

export type PreviewResponse = {
  schema_version?: string;
  mode: 'preview';
  school_level?: SchoolLevel;
  plan: PlanDoc;
  stats?: Record<string, unknown>;
};

// Unterstützte Foodgroups im UI und in der Auswertung.
export const FOOD_GROUPS = [
  '',
  'grains_potatoes',
  'vegetables',
  'legumes',
  'fruit',
  'dairy',
  'meat',
  'fish',
] as const;

export type FoodGroup = (typeof FOOD_GROUPS)[number];

// Anzeigenamen für die Foodgroup-Chips.
export const FOOD_GROUP_LABELS: Record<Exclude<FoodGroup, ''>, string> = {
  grains_potatoes: 'Getreide / Kartoffeln',
  vegetables: 'Gemüse / Salat',
  legumes: 'Hülsenfrüchte',
  fruit: 'Obst',
  dairy: 'Milch / Milchprodukte',
  meat: 'Fleisch / Wurst',
  fish: 'Fisch',
};

export const RELEVANT_TAGS = [
  'wholegrain',
  'potato_product',
  'raw_veg',
  'whole_fruit',
] as const;

export type RelevantTag = (typeof RELEVANT_TAGS)[number];

// Anzeigenamen für optionale Tags im Selbstcheck.
export const TAG_LABELS: Record<RelevantTag, string> = {
  wholegrain: 'Vollkorn',
  potato_product: 'Kartoffelerzeugnis (z. B. Püree, Kroketten, Pommes)',
  raw_veg: 'Rohkost (ungegart)',
  whole_fruit: 'Stückobst (kein Mus/Saft)',
};

export const FOOD_GROUP_STYLES: Record<
  Exclude<FoodGroup, ''>,
  { icon: string; color: string; bg: string }
> = {
  grains_potatoes: { icon: '🌾', color: '#b45309', bg: '#fef3c7' },
  vegetables: { icon: '🥦', color: '#15803d', bg: '#dcfce7' },
  legumes: { icon: '🫘', color: '#7c2d12', bg: '#fed7aa' },
  fruit: { icon: '🍎', color: '#991b1b', bg: '#fee2e2' },
  dairy: { icon: '🥛', color: '#0c4a6e', bg: '#e0f2fe' },
  meat: { icon: '🍖', color: '#7c2d12', bg: '#ffedd5' },
  fish: { icon: '🐟', color: '#164e63', bg: '#cffafe' },
};

// Fügt ein Tag hinzu oder entfernt es, wenn es bereits gesetzt ist.
export function toggleTag(
  list: string[] | undefined,
  tag: RelevantTag,
): string[] {
  const tags = Array.isArray(list) ? [...list] : [];
  if (tags.includes(tag)) return tags.filter((t) => t !== tag);
  tags.push(tag);
  return tags;
}

// Fügt eine Foodgroup hinzu oder entfernt sie, wenn sie bereits gesetzt ist.
export function toggleFoodGroup(
  list: string[] | undefined,
  fg: Exclude<FoodGroup, ''>,
): string[] {
  const groups = Array.isArray(list) ? [...list] : [];
  if (groups.includes(fg)) return groups.filter((g) => g !== fg);
  groups.push(fg);
  return groups;
}

// Liefert für Übersichten eine "primäre" Gruppe aus der Multi-Auswahl.
export function getPrimaryFoodGroup(item: PlanItem): string {
  const fromMulti = Array.isArray(item.food_groups)
    ? item.food_groups[0]
    : undefined;
  return (fromMulti ?? item.links?.food_group ?? '') as string;
}
