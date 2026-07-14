import { LegalPageLayout } from "@/components/shared/LegalPageLayout";

export default function TermsPage() {
  return (
    <LegalPageLayout title="Terms of use" subtitle="Rob's Finance — personal use only">
      <p>
        This application is provided for personal, non-commercial use by the account owner. It
        combines personal finance tracking with home solar and battery monitoring.
      </p>
      <p>
        Bank data is accessed read-only via Open Banking with your explicit consent at each
        connection. Energy system data is read from your inverter via a local adapter.
      </p>
      <p>
        You are responsible for keeping your login credentials secure. The app does not initiate
        payments or transfers on your behalf, and does not write changes to your inverter unless
        explicitly enabled by an administrator.
      </p>
      <p>
        The service is provided as-is without warranty. Use of Open Banking is subject to your
        bank&apos;s and Enable Banking&apos;s terms.
      </p>
    </LegalPageLayout>
  );
}
