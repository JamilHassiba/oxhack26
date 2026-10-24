import { scenarios, type DemoScenario } from './scenarios';
export function ScenarioPicker({
  value,
  onChange,
  disabled,
}: {
  value: DemoScenario;
  onChange: (value: DemoScenario) => void;
  disabled: boolean;
}) {
  return (
    <div className="demo-scenario">
      <label htmlFor="demo-scenario">Demo scenario</label>
      <select
        id="demo-scenario"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as DemoScenario)}
      >
        {Object.entries(scenarios).map(([id, scenario]) => (
          <option key={id} value={id}>
            {scenario.label}
          </option>
        ))}
      </select>
      <small>{scenarios[value].description}</small>
    </div>
  );
}
