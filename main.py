import wx
import xml.etree.ElementTree as ET
import os
import serial.tools.list_ports
import platform
import ctypes
import serial
import struct

# constants
CONFIG_FILE = "relay_settings.xml"
BAUD_RATE = 9600
BYTE_SIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOP_BITS = serial.STOPBITS_ONE
TIMEOUT = 1


def get_all_com_ports():
    """Get all COM ports including those in use"""
    ports = []
    # Try serial.tools.list_ports first
    detected_ports = serial.tools.list_ports.comports()
    for port in detected_ports:
        if port.description and port.description != port.device and port.description != "n/a":
            display_name = f"{port.device} - {port.description}"
        else:
            display_name = port.device
        ports.append(display_name)
    if platform.system() == 'Windows':
        try:
            import winreg
            path = r'HARDWARE\DEVICEMAP\SERIALCOMM'
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)

            registry_ports = []
            i = 0
            while True:
                try:
                    val = winreg.EnumValue(key, i)
                    registry_ports.append(val[1])  # COM port name
                    i += 1
                except WindowsError:
                    break
            winreg.CloseKey(key)
            existing_ports = [p.split(' - ')[0] if ' - ' in p else p for p in ports]
            for rport in registry_ports:
                if rport not in existing_ports:
                    ports.append(rport)
        except:
            pass

    return ports if ports else ["No ports found"]


def convert_to_bytes(format_type, data, float1=None, float2=None):
    """Convert stored data to bytes based on format type"""
    try:
        if format_type == "hex":
            # Parse hex string: "0x55 0x56 0x00" or "55 56 00" or "555600"
            if not data:
                return b''
            # Remove "0x" prefixes and spaces
            hex_str = data.replace('0x', '').replace(' ', '')
            # Convert hex string to bytes
            return bytes.fromhex(hex_str)

        elif format_type == "binary":
            # Parse binary string: "01010101 01010110" or "0101010101010110"
            if not data:
                return b''
            # Remove spaces
            binary_str = data.replace(' ', '')
            # Convert binary string to bytes (8 bits at a time)
            byte_list = []
            for i in range(0, len(binary_str), 8):
                byte_chunk = binary_str[i:i + 8]
                if len(byte_chunk) == 8:
                    byte_list.append(int(byte_chunk, 2))
            return bytes(byte_list)

        elif format_type == "32 bit float":
            # Convert two 32-bit floats to 8 bytes
            if not float1 or not float2:
                return b''

            result_bytes = b''

            # Process each float
            for float_str in [float1, float2]:
                # Check if it's hex bytes (8 hex chars = 4 bytes)
                if len(float_str.replace(' ', '').replace('0x', '')) == 8 and all(
                        c in '0123456789abcdefABCDEF x' for c in float_str):
                    # It's hex bytes - convert directly
                    hex_clean = float_str.replace(' ', '').replace('0x', '')
                    result_bytes += bytes.fromhex(hex_clean)
                else:
                    # It's a float value - pack it
                    try:
                        f_val = eval(float_str) if float_str.startswith('(') else float(float_str)
                        result_bytes += struct.pack('<f', f_val)
                    except:
                        f_val = float(float_str)
                        result_bytes += struct.pack('<f', f_val)

            print(f"DEBUG: Float1 input={float1!r}")
            print(f"DEBUG: Float2 input={float2!r}")
            print(f"DEBUG: Combined result: {result_bytes.hex()}")

            return result_bytes

        else:
            return b''

    except Exception as e:
        print(f"Error converting {format_type} data: {e}")
        return b''


class SettingsManager:
    def __init__(self):
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        """Load settings from XML file or create default if doesn't exist"""
        if os.path.exists(CONFIG_FILE):
            try:
                tree = ET.parse(CONFIG_FILE)
                root = tree.getroot()

                for channel_elem in root.findall('channel'):
                    channel = channel_elem.get('id')
                    for action_elem in channel_elem.findall('action'):
                        action = action_elem.get('type')
                        for format_elem in action_elem.findall('format'):
                            format_type = format_elem.get('type')

                            if format_type == 'c_float':
                                # Load two floats
                                for float_elem in format_elem.findall('float'):
                                    float_id = float_elem.get('id')
                                    value = float_elem.text or ""
                                    key = f"ch{channel}_{action}_c_float_{float_id}"
                                    self.settings[key] = value
                            else:
                                value = format_elem.text or ""
                                key = f"ch{channel}_{action}_{format_type}"
                                self.settings[key] = value

                print(f"Settings loaded from {CONFIG_FILE}")
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.create_default_settings()
        else:
            self.create_default_settings()
            self.save_settings()

    def create_default_settings(self):
        """Create default settings structure"""
        for channel in [1, 2]:
            for action in ['momentary', 'open', 'close', 'toggle']:
                for format_type in ['hex', 'binary']:
                    key = f"ch{channel}_{action}_{format_type}"
                    self.settings[key] = ""
                # Two floats for c_float type
                for float_num in [1, 2]:
                    key = f"ch{channel}_{action}_c_float_{float_num}"
                    self.settings[key] = ""

    def save_settings(self):
        """Save settings to XML file"""
        root = ET.Element('relay_settings')

        for channel in [1, 2]:
            channel_elem = ET.SubElement(root, 'channel', id=str(channel))

            for action in ['momentary', 'open', 'close', 'toggle']:
                action_elem = ET.SubElement(channel_elem, 'action', type=action)

                for format_type in ['hex', 'binary']:
                    key = f"ch{channel}_{action}_{format_type}"
                    format_elem = ET.SubElement(action_elem, 'format', type=format_type)
                    format_elem.text = self.settings.get(key, '')

                # Two floats for c_float type
                c_float_elem = ET.SubElement(action_elem, 'format', type='c_float')
                for float_num in [1, 2]:
                    key = f"ch{channel}_{action}_c_float_{float_num}"
                    float_elem = ET.SubElement(c_float_elem, 'float', id=str(float_num))
                    float_elem.text = self.settings.get(key, '')

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(CONFIG_FILE, encoding='utf-8', xml_declaration=True)
        print(f"Settings saved to {CONFIG_FILE}")

    def get(self, key, default=''):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value

    def update_all(self, new_settings):
        self.settings.update(new_settings)
        self.save_settings()


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, settings_manager):
        super().__init__(parent, title="Command Settings", size=(600, 650))

        self.settings_manager = settings_manager
        self.temp_settings = {}

        # Copy current settings to temp
        for key in settings_manager.settings:
            self.temp_settings[key] = settings_manager.get(key)

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create scrolled window for settings
        scroll = wx.ScrolledWindow(panel)
        scroll.SetScrollRate(5, 5)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        self.text_ctrls = {}

        # Add text controls for each command
        for channel in [1, 2]:
            channel_label = wx.StaticText(scroll, label=f"Channel {channel}")
            font = channel_label.GetFont()
            font.PointSize += 2
            font = font.Bold()
            channel_label.SetFont(font)
            scroll_sizer.Add(channel_label, 0, wx.ALL, 10)

            for action in ['momentary', 'open', 'close', 'toggle']:
                action_label = wx.StaticText(scroll, label=f"  {action.capitalize()}:")
                action_font = action_label.GetFont()
                action_font = action_font.Bold()
                action_label.SetFont(action_font)
                scroll_sizer.Add(action_label, 0, wx.LEFT | wx.TOP, 10)

                for format_type in ['hex', 'binary']:
                    key = f"ch{channel}_{action}_{format_type}"

                    label = wx.StaticText(scroll, label=f"    {format_type.upper()}:")
                    scroll_sizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

                    text_ctrl = wx.TextCtrl(scroll, value=self.temp_settings.get(key, ''))
                    scroll_sizer.Add(text_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                    self.text_ctrls[key] = text_ctrl

                # Two 32-bit floats
                label = wx.StaticText(scroll, label=f"    32 BIT FLOAT:")
                scroll_sizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

                float_sizer = wx.BoxSizer(wx.HORIZONTAL)
                for float_num in [1, 2]:
                    key = f"ch{channel}_{action}_c_float_{float_num}"

                    float_label = wx.StaticText(scroll, label=f"Float {float_num} (or hex bytes):")
                    float_sizer.Add(float_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

                    text_ctrl = wx.TextCtrl(scroll, value=self.temp_settings.get(key, ''),
                                            size=(140, -1), style=wx.TE_LEFT)
                    float_sizer.Add(text_ctrl, 0, wx.LEFT | wx.RIGHT, 5)

                    self.text_ctrls[key] = text_ctrl

                scroll_sizer.Add(float_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

            scroll_sizer.Add(wx.StaticLine(scroll), 0, wx.EXPAND | wx.ALL, 5)

        scroll.SetSizer(scroll_sizer)
        main_sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_exit_btn = wx.Button(panel, label="Save and Exit")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btn_sizer.Add(save_exit_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        save_exit_btn.Bind(wx.EVT_BUTTON, self.on_save_exit)

    def on_save_exit(self, event):
        # Update temp settings from text controls
        for key, ctrl in self.text_ctrls.items():
            value = ctrl.GetValue()

            # For c_float type, just validate and store as-is (can be float or hex)
            if '_c_float_' in key and value:
                # Check if it's hex format
                clean_val = value.replace(' ', '').replace('0x', '')
                if len(clean_val) == 8 and all(c in '0123456789abcdefABCDEF' for c in clean_val):
                    # It's hex - store as-is
                    self.temp_settings[key] = value
                else:
                    # It's a float - validate and store
                    try:
                        float(value)
                        self.temp_settings[key] = value
                    except ValueError:
                        wx.MessageBox(f"Invalid value for {key}: {value}\nMust be a valid float or 8-digit hex.",
                                      "Validation Error", wx.OK | wx.ICON_ERROR)
                        return
            else:
                self.temp_settings[key] = value

        # Save to settings manager and file
        self.settings_manager.update_all(self.temp_settings)

        self.EndModal(wx.ID_OK)


class ChannelControlPanel(wx.Panel):
    def __init__(self, parent, channel_num, on_command):
        super().__init__(parent)
        self.channel_num = channel_num
        self.on_command = on_command

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Channel label
        label = wx.StaticText(self, label=f"Channel {channel_num}")
        label.SetFont(label.GetFont().Bold())
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        # Buttons
        for action in ['Momentary', 'Open', 'Close', 'Toggle']:
            btn = wx.Button(self, label=action)
            btn.Bind(wx.EVT_BUTTON, lambda e, a=action.lower(): self.on_button_click(a))
            sizer.Add(btn, 0, wx.EXPAND | wx.ALL, 3)

        self.SetSizer(sizer)

    def on_button_click(self, action):
        self.on_command(self.channel_num, action)


class FormatRegionPanel(wx.Panel):
    def __init__(self, parent, format_name, on_command):
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self.format_name = format_name
        self.on_command = on_command

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Region label
        label = wx.StaticText(self, label=format_name.upper())
        font = label.GetFont()
        font.PointSize += 1
        font = font.Bold()
        label.SetFont(font)
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 8)

        # Channels side by side
        channel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        ch1_panel = ChannelControlPanel(self, 1, self.handle_command)
        ch2_panel = ChannelControlPanel(self, 2, self.handle_command)

        channel_sizer.Add(ch1_panel, 1, wx.EXPAND | wx.ALL, 5)
        channel_sizer.Add(ch2_panel, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(channel_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

    def handle_command(self, channel, action):
        self.on_command(channel, action, self.format_name)


class RelayControlFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="RS232 Relay Control", size=(800, 850))

        self.com_open = False
        self.ser = None

        # Initialize settings manager (loads from XML or creates default)
        self.settings_manager = SettingsManager()

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Top control bar
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # COM port section
        com_label = wx.StaticText(panel, label="COM:")
        top_sizer.Add(com_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        # Get all COM ports
        self.available_ports = get_all_com_ports()

        self.com_choice = wx.Choice(panel, choices=self.available_ports, size=(300, -1))
        if len(self.available_ports) > 0 and self.available_ports[0] != "No ports found":
            self.com_choice.SetSelection(0)
        top_sizer.Add(self.com_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.com_btn = wx.Button(panel, label="Open")
        self.com_btn.Bind(wx.EVT_BUTTON, self.on_com_toggle)
        top_sizer.Add(self.com_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        top_sizer.AddStretchSpacer()

        # Settings button
        settings_btn = wx.Button(panel, label="Settings")
        settings_btn.Bind(wx.EVT_BUTTON, self.on_settings)
        top_sizer.Add(settings_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Format regions
        self.hex_region = FormatRegionPanel(panel, "hex", self.on_command)
        main_sizer.Add(self.hex_region, 1, wx.EXPAND | wx.ALL, 10)

        self.binary_region = FormatRegionPanel(panel, "binary", self.on_command)
        main_sizer.Add(self.binary_region, 1, wx.EXPAND | wx.ALL, 10)

        self.string_region = FormatRegionPanel(panel, "32 bit float", self.on_command)
        main_sizer.Add(self.string_region, 1, wx.EXPAND | wx.ALL, 10)

        # Sent display section at bottom
        sent_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sent_label = wx.StaticText(panel, label="Sent:")
        font = sent_label.GetFont()
        font = font.Bold()
        sent_label.SetFont(font)
        sent_sizer.Add(sent_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.sent_display = wx.StaticText(panel, label="")
        self.sent_display.SetForegroundColour(wx.Colour(0, 100, 0))
        sent_sizer.Add(self.sent_display, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        main_sizer.Add(sent_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(main_sizer)

        self.Centre()

    def on_com_toggle(self, event):
        if self.com_open:
            if self.ser:
                self.ser.close()
            self.com_open = False
            self.com_btn.SetLabel("Open")
            self.com_choice.Enable()
            selected_port = self.com_choice.GetStringSelection()
            # Extract just the COM port name (before the dash if present)
            port_name = selected_port.split(' - ')[0] if ' - ' in selected_port else selected_port
            print(f"Closed {port_name}")
        else:
            com_port = self.com_choice.GetStringSelection()
            # Extract just the COM port name (before the dash if present)
            port_name = com_port.split(' - ')[0] if ' - ' in com_port else com_port
            if com_port and com_port != "No ports found":
                try:
                    self.ser = serial.Serial(
                        port=port_name,
                        baudrate=BAUD_RATE,
                        bytesize=BYTE_SIZE,
                        parity=PARITY,
                        stopbits=STOP_BITS,
                        timeout=TIMEOUT
                    )
                    self.com_open = True
                    self.com_btn.SetLabel("Close")
                    self.com_choice.Disable()
                    print(f"Opened {port_name}")
                except Exception as e:
                    wx.MessageBox(f"Error opening COM port: {e}", "Error", wx.OK | wx.ICON_ERROR)
                    self.com_open = False
                    self.com_btn.SetLabel("Open")
                    self.com_choice.Enable()
            else:
                wx.MessageBox("Please select a valid COM port", "Error", wx.OK | wx.ICON_ERROR)

    def on_settings(self, event):
        dlg = SettingsDialog(self, self.settings_manager)
        if dlg.ShowModal() == wx.ID_OK:
            print("Settings saved and updated")
        dlg.Destroy()

    def on_command(self, channel, action, format_type):
        # Get data based on format type
        if format_type == "32 bit float":
            # Get both floats
            key1 = f"ch{channel}_{action}_c_float_1"
            key2 = f"ch{channel}_{action}_c_float_2"
            float1 = self.settings_manager.get(key1, '')
            float2 = self.settings_manager.get(key2, '')
            display_command = f"Float1: {float1}, Float2: {float2}"

            # Convert to bytes
            byte_data = convert_to_bytes(format_type, None, float1, float2)
        else:
            format_key = format_type
            key = f"ch{channel}_{action}_{format_key}"
            command_str = self.settings_manager.get(key, '')
            display_command = command_str

            # Convert to bytes
            byte_data = convert_to_bytes(format_type, command_str)

        # Display button click
        button_name = f"Channel {channel} - {action.capitalize()} - {format_type.upper()}"
        display_text = f"Button [{button_name}] clicked"
        if display_command:
            display_text += f" - Data: {display_command}"
            # Show hex representation of bytes
            if byte_data:
                hex_repr = ' '.join(f'0x{b:02X}' for b in byte_data)
                display_text += f" - Bytes: {hex_repr}"
        self.sent_display.SetLabel(display_text)

        print(f"Command: Channel {channel}, Action: {action}, Format: {format_type}")
        print(f"Display: {display_command}")
        print(f"Bytes to send: {byte_data.hex() if byte_data else 'None'}")

        if self.com_open:
            if byte_data:
                try:
                    self.ser.write(byte_data)
                    print(f"Sent {len(byte_data)} bytes to serial port")
                except Exception as e:
                    wx.MessageBox(f"Error sending data: {e}", "Serial Error", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("No data to send. Please configure settings.", "Warning", wx.OK | wx.ICON_WARNING)
        else:
            wx.MessageBox("COM port is not open", "Warning", wx.OK | wx.ICON_WARNING)


def main():
    app = wx.App()
    frame = RelayControlFrame()
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()