import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const resources = {
  fr: {
    translation: {
      "chat.placeholder": "Discutez avec l'agent",
      "chat.send": "Envoyer"
    }
  },
  en: {
    translation: {
      "chat.placeholder": "Chat with the agent",
      "chat.send": "Send"
    }
  }
};

i18n.use(initReactI18next).init({
  resources,
  lng: "fr",
  interpolation: { escapeValue: false }
});

export default i18n;
