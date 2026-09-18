import styles from './App.module.css';

export default function App() {
  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <a className={styles.brand} href="/" aria-label="MetroPulse home">
          M<span>MetroPulse</span>
        </a>
        <span className={styles.tag}>NYC / YELLOW TAXI</span>
      </header>
      <section className={styles.hero} aria-labelledby="headline">
        <p className={styles.eyebrow}>URBAN MOBILITY INTELLIGENCE</p>
        <h1 id="headline">
          Every trip tells
          <br />a city’s story.
        </h1>
        <p className={styles.intro}>
          Exploring New York’s taxi demand, neighborhood activity, and the
          patterns that move a city.
        </p>
        <div className={styles.status}>
          <span aria-hidden="true" />
          Milestone 1 · Project foundation
        </div>
      </section>
      <section className={styles.grid} aria-label="Project scope">
        <article>
          <p className={styles.number}>01 / SOURCE</p>
          <h2>Public data. Clear provenance.</h2>
          <p>
            Official NYC TLC Yellow Taxi records. The initial analysis window is
            January–March 2025.
          </p>
          <a href="https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page">
            Explore the source ↗
          </a>
        </article>
        <article>
          <p className={styles.number}>02 / FOUNDATION</p>
          <h2>Reliable from the first byte.</h2>
          <p>
            A streaming downloader with checksums and retries establishes a
            reproducible starting point.
          </p>
        </article>
        <article>
          <p className={styles.number}>03 / COMING NEXT</p>
          <h2>From records to insight.</h2>
          <p>
            Validation, analytics, forecasting, and pipeline health will arrive
            in later milestones. Live metrics are not connected yet.
          </p>
        </article>
      </section>
      <footer>
        Historical mobility analytics · Not a live GPS tracker
        <span>METROPULSE / 2025 DATA</span>
      </footer>
    </main>
  );
}
