type Props = {
  label: string;
};

export default function SectionLoader({ label }: Props) {
  return (
    <div className="section-loader" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
