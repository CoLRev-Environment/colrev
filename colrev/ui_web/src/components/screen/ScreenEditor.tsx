import Screen from "../../models/screen";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const ScreenEditor: React.FC<{
  screen: Screen;
  screenChanged: any;
}> = ({ screen, screenChanged }) => {
  const screenScriptsChangedHandler = (scripts: Script[]) => {
    const newScreen = { ...screen, scripts: scripts };
    screenChanged(newScreen);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          packageType="screen_scripts"
          scripts={screen.scripts}
          scriptsChanged={(scripts: Script[]) =>
            screenScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default ScreenEditor;
