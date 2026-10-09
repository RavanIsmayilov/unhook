/** "How to recognize this scam": general advice per scheme, shown under a verdict and on the radar. No statistics. */
export const TIPS: Record<string, { title: string; flags: string[] }> = {
  fake_bonus: {
    title: "Saxta bonus və uduş",
    flags: [
      "Heç nə etməmiş “bonus”, “hədiyyə” və ya “uduş” qazandığınızı deyirlər.",
      "Operator və bank bonusları yalnız rəsmi tətbiq, rəsmi sayt və ya rəsmi nömrə ilə gəlir.",
      "Linkdəki ünvan rəsmi saytla eyni deyil: oxşardır (məs. azercel1.com, azercell-bonus.top).",
    ],
  },
  bank_impersonation: {
    title: "Bank adından fişinq",
    flags: [
      "“Kartınız bloklandı, təcili təsdiqləyin” deyərək sizi tələsdirirlər.",
      "Kart nömrəsi, CVV, PIN və ya SMS kodu istəyirlər. Bank bunları heç vaxt istəmir.",
      "Bank sizi linkə yox, rəsmi tətbiqə və ya kartın arxasındakı nömrəyə yönləndirir.",
    ],
  },
  fake_job: {
    title: "Saxta iş elanı",
    flags: [
      "Təcrübəsiz yüksək gəlir vəd edirlər.",
      "İşə başlamazdan əvvəl “qeydiyyat haqqı” və ya “depozit” köçürməyi tələb edirlər.",
      "Yalnız WhatsApp və ya Telegram-da yazışırlar, şirkətin rəsmi ünvanı və müqaviləsi yoxdur.",
    ],
  },
  delivery_scam: {
    title: "Çatdırılma fırıldağı",
    flags: [
      "Gözləmədiyiniz bağlama üçün kiçik məbləğ (gömrük, çatdırılma) ödəməyi xahiş edirlər.",
      "Ödəniş linki poçtun və ya kuryerin rəsmi saytı deyil.",
      "Bağlama izləmə kodunu rəsmi saytda yoxlayın, mesajdakı linkdə yox.",
    ],
  },
  investment_scam: {
    title: "İnvestisiya fırıldağı",
    flags: [
      "Qısa müddətdə “zəmanətli” və ya çox yüksək qazanc vəd edirlər.",
      "Pulu dərhal qoymağınızı və qrupa qoşulmağınızı təkid edirlər.",
      "Lisenziyalı şirkət zəmanətli gəlir vəd etmir. Vəd varsa, ehtiyatlı olun.",
    ],
  },
  other: {
    title: "Fırıldaq əlamətləri",
    flags: [
      "Sizi tələsdirirlər: “indi”, “təcili”, “24 saat ərzində”.",
      "Pul köçürməyi, link açmağı və ya kod söyləməyi istəyirlər.",
      "Tanış adından yazırlar, amma nömrə yenidir. Əvvəlcə həmin şəxsə başqa yolla zəng edin.",
    ],
  },
};

export const tipFor = (scheme: string) => TIPS[scheme] ?? TIPS.other;
