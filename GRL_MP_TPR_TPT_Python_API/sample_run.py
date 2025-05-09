# sample_grl_api_usage.py
import json

from client.grl_api_client import GRLApiClient


def main():
    # Initialize the client
    client = GRLApiClient(
        config_file_path="grl_config.json",
    )

    try:
        # Step 1: Launch the GRL Application
        if client.launch_app():
            print("Application launched successfully!")

            # Step 2: Connect to Test Equipment
            connection_result = client.connect("192.168.5.53")
            #connection_result = client.connect("192.168.5.9")
            if "error" in connection_result:
                print(f"Connection failed: {connection_result['error']}")
                return
            else:
                success_data = connection_result.get("success")
                print("Connected to Test Equipment successfully!")
                if isinstance(success_data, dict):
                    print(f"Tester Status: {success_data.get('testerStatus')}")
                    print(f"Firmware Version: {success_data.get('firmwareVersion')}")

            # Step 3: Create project
            client.set_project()

            test_config_new = ["7.1 MPP.PTX.POW.Digital_Ping_128kHz_P1", "7.2 MPP."
                               "PTX.POW.Digital_Ping_360kHz_P1",
                               "14.1.5 MPP.PTX.FOD.MATEDQ_PREPOWER_DETECTION.TC1",
                               "7.1 MPP.PTX.POW.Digital_Ping_128kHz_P1",
                               "7.2 MPP.PTX.POW.Digital_Ping_360kHz_P1",
                               "7.3 MPP.PTX_POW_Cloak_Ping_360_LPM_TC1", ]
            test_config = ["14.1.5 MPP.PTX.FOD.MATEDQ_PREPOWER_DETECTION.TC1"]
            # test_config = ["9.10 MPP.PTX.POW.GUARANTEED_POWER.MPP25_P1"]
            selected_test = [
                "7.1 MPP.PTX.POW.Digital_Ping_128kHz_P1",
                "7.2 MPP.PTX.POW.Digital_Ping_360kHz_P1",
                "7.3 MPP.PTX_POW_Cloak_Ping_360_LPM_TC1",
                "8.1 MPP.PTX.POW.K-Est_P1",
                "9.1 MPP.PTX.POW.GUARANTEED_POWER.P1",
                "9.2 MPP.PTX.POW.VRECT_CONTROL_P1_1",
                "11.1 MPP.PTX.PHY.ASK_DEMOD.ILOAD_P1",
                "11.1 MPP.PTX.PHY.ASK_DEMOD.RAC_P1",
                "12.2.1 MPP.PTX.CPX.PNG.RX_IDENTIFICATION.TC1",
                "12.2.2 MPP.PTX.CPX.PNG.RX_IDENTIFICATION.TC2",
                "12.3.1 MPP.PTX.CPX.NEG.ERROR_STATUS.TC1",
                "12.3.1 MPP.PTX.CPX.NEG.ERROR_STATUS.TC2",
                "12.4.1 MPP.PTX.CPX.POW.XCE_HANDLING.TC1",
                "12.4.1 MPP.PTX.CPX.POW.XCE_HANDLING.TC1a",
                "12.5.1 MPP.PTX.CPX.CLOAK.ENTER_CLOAK_TC1",
                "12.5.1 MPP.PTX.CPX.CLOAK.ENTER_CLOAK_TC2",
                "14.1.1 MPP.PTX.FOD.BEFOREPOWER_FO_PRESENT.TC1g",
                "14.1.1 MPP.PTX.FOD.BEFOREPOWER_FO_PRESENT.TC1i",
                "14.2.1 MPP.PTX.FOD.MPLA_PARAM_CHECK",
                "14.2.2 MPP.PTX.FOD.RESPONSE_VALID_DEVICE.TC1.P1"
            ]
            with open('Test_Case_List_From_System/Generated_Test_cases_list.json', 'r') as file:
                selected_test_cases = json.load(file)
            # Step 4: Run test cases

            selected_test = [
                "7.1 MPP.PTX.POW.Digital_Ping_128kHz_P1",
                "7.2 MPP.PTX.POW.Digital_Ping_360kHz_P1",
                "7.3 MPP.PTX_POW_Cloak_Ping_360_LPM_TC1",
                "8.1 MPP.PTX.POW.K-Est_P1",
                "9.1 MPP.PTX.POW.GUARANTEED_POWER.P1"]
            client.submit_test_list(test_config_new)



        else:
            print("Failed to launch GRL application.")

    except Exception as e:
        print(f"Exception occurred: {str(e)}")

    finally:
        # Step 5: Always disconnect at the end
        client.disconnect()
        print("Disconnected cleanly.")


if __name__ == "__main__":
    main()
