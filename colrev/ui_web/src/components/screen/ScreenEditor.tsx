import { useEffect, useState } from "react";
import Screen from "../../models/screen";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const ScreenEditor: React.FC<{
  screen: Screen;
  screenChanged: any;
}> = ({ screen, screenChanged }) => {
  const [explanation, setExplanation] = useState<string | null>(null);

  useEffect(() => {
    if (screen) {
      setExplanation(screen.explanation);
    }
  }, [screen]);

  const explanationChangedHandler = (event: any) => {
    let newValue = event.target.value;

    if (!newValue) {
      newValue = null;
    }

    const newScreen = { ...screen, explanation: newValue };
    screenChanged(newScreen);
  };

  const screenScriptsChangedHandler = (scripts: Package[]) => {
    const newScreen = { ...screen, scripts: scripts };
    screenChanged(newScreen);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="screenExplanation">Explanation</label>
        <input
          className="form-control"
          type="text"
          id="screenExplanation"
          value={explanation ?? ""}
          onChange={explanationChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="screen"
          packages={screen.scripts}
          packagesChanged={(scripts: Package[]) =>
            screenScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default ScreenEditor;
