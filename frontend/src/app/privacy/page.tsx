import { LegalPageLayout } from "@/components/shared/LegalPageLayout";

export default function PrivacyPage() {
  return (
    <LegalPageLayout title="Privacy policy" subtitle="Rob's Finance — personal use only">
      <p>
        This app is a private dashboard for personal finance and home energy monitoring. Bank
        connection data is read-only and used solely to display your account balances and
        transactions within the app.
      </p>
      <p>
        Energy data from your inverter is stored locally on your backend server and used only to
        display generation, consumption, and savings insights within the app.
      </p>
      <p>
        Open Banking credentials and session tokens are stored securely on the backend server.
        They are not shared with third parties except Enable Banking and your chosen bank during
        the authorised connection flow.
      </p>
      <p>
        For questions about this policy, contact the account owner via the email registered with
        Enable Banking.
      </p>
    </LegalPageLayout>
  );
}
