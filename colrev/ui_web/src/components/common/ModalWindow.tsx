import { Modal } from "bootstrap";
import { useEffect, useRef } from "react";
import ReactDOM from "react-dom";

const portalElement: any = document.getElementById("overlays");

const ModalWindow: React.FC<{
  title: string;
  isShowOk: boolean;
  isOkEnabled: boolean;
  onOk: any;
  onCancel: any;
  children: any;
}> = ({ title, isShowOk, isOkEnabled, onOk, onCancel, children }) => {
  const modalRef = useRef<any>();

  const showModal = () => {
    const modalElement = modalRef.current;

    let modal = Modal.getInstance(modalElement);
    if (!modal) {
      modal = new Modal(modalElement, {
        backdrop: "static",
        keyboard: false,
      });
    }

    modal.show();
  };

  const hideModal = () => {
    const modalElement = modalRef.current;
    const modal = Modal.getInstance(modalElement);
    modal?.hide();
  };

  const cancleHandler = () => {
    hideModal();
    onCancel();
  };

  const okHandler = () => {
    hideModal();
    onOk();
  };

  useEffect(() => {
    showModal();
  }, []);

  return (
    <>
      {ReactDOM.createPortal(
        <div className="modal fade" ref={modalRef} tabIndex={-1}>
          <div className="modal-dialog modal-lg">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">{title}</h5>
                <button
                  type="button"
                  className="btn-close"
                  onClick={cancleHandler}
                  aria-label="Close"
                ></button>
              </div>
              <div className="modal-body">{children}</div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={cancleHandler}
                >
                  Cancel
                </button>
                {isShowOk && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!isOkEnabled}
                    onClick={okHandler}
                  >
                    Ok
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>,
        portalElement
      )}
    </>
  );
};

export default ModalWindow;
