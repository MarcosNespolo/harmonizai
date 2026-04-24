"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import { WineList } from "./components/WineList";
import { MOCK_WINES, type Wine, type WineListState } from "./lib/wines";

const EXAMPLES = ["Sushi", "Risoto", "Churrasco", "Salmão grelhado"];

export default function Home() {
  const [input, setInput] = useState("");
  const [listState, setListState] = useState<WineListState>("empty");
  const [wines, setWines] = useState<Wine[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSubmit = input.trim().length > 0 && listState !== "loading";
  const isPopulated = listState === "populated";

  const runSearch = () => {
    if (!canSubmit) return;
    setListState("loading");
    setWines([]);
    setTimeout(() => {
      setWines(MOCK_WINES);
      setListState("populated");
    }, 1500);
  };

  const handleReset = () => {
    setInput("");
    setWines([]);
    setListState("empty");
    textareaRef.current?.focus();
  };

  const pickExample = (example: string) => {
    setInput(example);
    textareaRef.current?.focus();
  };

  return (
    <div className="grid min-h-dvh grid-rows-[auto_1fr] gap-8 p-6 sm:p-8 lg:p-10">
      <header className="flex items-center gap-3 sm:gap-4">
        <Image
          src="/logo.svg"
          alt=""
          width={112}
          height={112}
          priority
          style={{ width: "var(--size-logo)", height: "auto" }}
          aria-hidden
        />
        <div className="flex flex-col">
          <h1
            className="font-bold leading-none tracking-tight text-2xl"
          >
            <span className="text-primary">Harmoniz</span>
            <span className="text-secondary">AI</span>
          </h1>
          <p
            className="mt-1 text-ink-muted text-sm"
          >
            Descubra o vinho ideal para sua refeição.
          </p>
        </div>
      </header>

      <main className="mx-auto grid w-fit gap-8 lg:grid-cols-2 lg:gap-16">
        <section className="flex items-center justify-center lg:justify-end">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runSearch();
            }}
            className="flex w-full sm:min-w-[560px] max-w-[560px] flex-col gap-3"
          >
            <label
              htmlFor="dish"
              className="text-ink-muted cursor-pointer"
              style={{ fontSize: "var(--text-prompt)" }}
            >
              O que você vai comer hoje?
            </label>

            <div
              className="relative rounded-xl border border-border bg-card shadow-[0_1px_2px_rgba(20,20,20,0.04)] transition focus-within:border-primary/40 focus-within:shadow-[0_0_0_3px_rgba(91,12,27,0.08)]"
              style={{ padding: "var(--size-card-pad)" }}
            >
              <textarea
                id="dish"
                ref={textareaRef}
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    runSearch();
                  }
                }}
                placeholder="Descreva seu prato…"
                className="w-full resize-none border-0 bg-transparent text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-subtle"
              />

              <div className="mt-1 flex items-center justify-between gap-2">
                {isPopulated ? (
                  <button
                    type="button"
                    onClick={handleReset}
                    className="text-[12px] text-ink-subtle transition hover:text-primary cursor-pointer"
                  >
                    Nova busca
                  </button>
                ) : (
                  <span />
                )}
                <button
                  type="submit"
                  disabled={!canSubmit}
                  aria-label="Harmonizar"
                  className="inline-flex h-9 items-center gap-1.5 rounded-full bg-primary pl-3.5 pr-3 text-[13px] font-medium text-white transition hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-ink-subtle/40 disabled:text-white cursor-pointer"
                >
                  {listState === "loading" ? "Harmonizando…" : "Harmonizar"}
                  {listState !== "loading" && (
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden
                      className="h-3.5 w-3.5"
                    >
                      <path d="M5 12h14" />
                      <path d="m13 6 6 6-6 6" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => pickExample(ex)}
                  className="rounded-full border border-border/70 bg-transparent px-2.5 py-1 text-[12px] text-ink-muted transition hover:border-primary/30 hover:text-primary cursor-pointer"
                >
                  {ex}
                </button>
              ))}
            </div>
          </form>
        </section>

        <aside className="flex w-full items-center">
          <WineList state={listState} wines={wines} />
        </aside>
      </main>
    </div>
  );
}
