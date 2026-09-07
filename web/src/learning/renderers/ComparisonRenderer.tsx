import type { ComparisonLearningObject } from "../schema/learningObject"
import styles from "./comparisonRenderer.module.css"

export function ComparisonRenderer({ object }: { object: ComparisonLearningObject }) {
  const attributeLabels = [...new Set(object.items.flatMap((item) => item.attributes.map((attribute) => attribute.label)))]
  return (
    <div className={styles.wrapper}>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Attribute</th>
              {object.items.map((item) => <th scope="col" key={item.id}>{item.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {attributeLabels.map((label) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                {object.items.map((item) => <td key={item.id}>{item.attributes.find((attribute) => attribute.label === label)?.value ?? "—"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {object.similarities?.length ? <section><h3>Similarities</h3><ul>{object.similarities.map((value) => <li key={value}>{value}</li>)}</ul></section> : null}
      {object.differences?.length ? <section><h3>Differences</h3><ul>{object.differences.map((value) => <li key={value}>{value}</li>)}</ul></section> : null}
    </div>
  )
}
