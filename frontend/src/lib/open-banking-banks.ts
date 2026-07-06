import type { OpenBankingInstitution } from "@/lib/finance-schemas";

export type PersonalBankOption = {
  label: string;
  searchQuery: string;
  /** Sandbox Mock ASPSP only — real GB banks need Restricted Production. */
  sandboxInstitution?: OpenBankingInstitution;
};

export const PERSONAL_BANK_OPTIONS: PersonalBankOption[] = [
  {
    label: "Mock ASPSP",
    searchQuery: "Mock ASPSP",
    sandboxInstitution: { id: "FI:Mock ASPSP", name: "Mock ASPSP", logo: "" },
  },
  { label: "Lloyds", searchQuery: "Lloyds" },
  { label: "Halifax", searchQuery: "Halifax" },
  { label: "Bank of Scotland", searchQuery: "Bank of Scotland" },
  { label: "Virgin Money", searchQuery: "Virgin Money" },
  { label: "MBNA", searchQuery: "MBNA" },
  { label: "Barclays", searchQuery: "Barclays" },
  { label: "Nationwide", searchQuery: "Nationwide" },
  { label: "NatWest", searchQuery: "NatWest" },
  { label: "Royal Bank of Scotland", searchQuery: "Royal Bank of Scotland" },
  { label: "HSBC", searchQuery: "HSBC" },
  { label: "Monzo", searchQuery: "Monzo" },
  { label: "Starling", searchQuery: "Starling" },
];

export function isBankLinked(linkedBanks: string[], bankLabel: string): boolean {
  const needle = bankLabel.toLowerCase();
  return linkedBanks.some((name) => name.toLowerCase().includes(needle) || needle.includes(name.toLowerCase()));
}
