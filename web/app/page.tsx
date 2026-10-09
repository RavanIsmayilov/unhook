import { CheckForm } from "@/components/CheckForm";

export default function Home() {
  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-6 text-center sm:mb-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Fırıldaqçıya tutulmadan əvvəl xilas ol</h1>
        <p className="mt-3 text-ink2">
          Şübhəli mesajı və ya ekran görüntüsünü göndərin. Fırıldaqdırmı, hansı üsuldur və nə etmək lazımdır, deyək.
          Azərbaycan dilində, translitlə və rus dili qarışıq mətnləri başa düşürük.
        </p>
      </div>
      <CheckForm />
      <a href="/challenge" className="mt-6 block rounded-2xl border border-line bg-surface p-4 text-center hover:bg-page">
        <span className="font-semibold">🎮 Unhook-u aldada bilərsən?</span>
        <span className="block text-sm text-ink2">Fırıldaq mesajı yaz, görək tanıyacaq?</span>
      </a>
      <p className="mt-4 text-center text-sm text-ink2">
        Telegram-da da yoxlaya bilərsiniz:{" "}
        <a href="https://t.me/unhook_az_bot" className="font-medium text-s1 underline underline-offset-2">@unhook_az_bot</a>
      </p>
    </div>
  );
}
