export type WineListState = "empty" | "loading" | "populated";

export interface Wine {
  id: string;
  name: string;
  winery: string;
  vintage: number;
  region: string;
  matchScore: number;
  matchLabel: string;
  notes: string;
  color: string;
}

export const MOCK_WINES: Wine[] = [
  {
    id: "1",
    name: "Cabernet Sauvignon Reserva",
    winery: "Viña Errázuriz",
    vintage: 2019,
    region: "Chile · Valle del Aconcagua",
    matchScore: 94,
    matchLabel: "Excelente",
    notes: "Corpo encorpado, taninos firmes, notas de cassis e especiarias.",
    color: "#5b0c1b",
  },
  {
    id: "2",
    name: "Malbec Edición Limitada",
    winery: "Catena Zapata",
    vintage: 2020,
    region: "Argentina · Mendoza",
    matchScore: 88,
    matchLabel: "Muito boa",
    notes: "Frutado intenso, taninos aveludados, final persistente.",
    color: "#7a2b33",
  },
  {
    id: "3",
    name: "Pinot Noir Gran Reserva",
    winery: "Miguel Torres",
    vintage: 2021,
    region: "Chile · Valle de Curicó",
    matchScore: 81,
    matchLabel: "Boa",
    notes: "Leve, elegante, notas de cereja e terra molhada.",
    color: "#8b3a3a",
  },
];
