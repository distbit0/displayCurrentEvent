import tkinter as tk
import time
import threading


def display_dialog(message, display_time):
    """
    Displays a dialog box with a given message for a specified amount of time.

    :param message: The message to be displayed in the dialog box.
    :param display_time: Time in seconds for which the dialog is displayed.
    """

    def on_close():
        pass  # Disable close functionality

    # Create the main window
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Create a top-level window for the dialog
    dialog_window = tk.Toplevel(root)
    dialog_window.title("Message")
    dialog_window.protocol("WM_DELETE_WINDOW", on_close)  # Disable the close button

    # Position the dialog in the center of the screen
    dialog_window.geometry(
        "+{}+{}".format(
            root.winfo_screenwidth() // 2 - dialog_window.winfo_reqwidth() // 2,
            root.winfo_screenheight() // 2 - dialog_window.winfo_reqheight() // 2,
        )
    )

    # Display the message
    tk.Label(dialog_window, text=message, padx=20, pady=20).pack()

    # Function to close the dialog after a delay
    def close_dialog():
        time.sleep(display_time)
        dialog_window.destroy()
        root.quit()

    # Run the closing function in a separate thread
    threading.Thread(target=close_dialog).start()

    root.mainloop()


# Example usage
display_dialog("This message will disappear after 5 seconds", 5)
