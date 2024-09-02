from state_management import configure_device
from state_management.utils.interval import clear_all
from view.textualUI.main import Main_UI


def main():
    try:
        Main_UI().run()
    except Exception as e:
        clear_all()
        raise


if __name__ == "__main__":
    configure_device("src/raspi/pinconfig.json")
    main()
