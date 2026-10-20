import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tutor CRM",
    short_name: "Tutor CRM",
    description: "Локальная CRM преподавателя и учеников",
    start_url: "/",
    display: "standalone",
    background_color: "#202124",
    theme_color: "#202124",
    lang: "ru",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
