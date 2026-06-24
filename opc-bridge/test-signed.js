const { OPCUAClient, MessageSecurityMode, SecurityPolicy } = require("node-opcua");

const client = OPCUAClient.create({
  endpointMustExist: false,
  securityMode: MessageSecurityMode.Sign,
  securityPolicy: SecurityPolicy.Basic256Sha256,
  connectionStrategy: { maxRetry: 1, initialDelay: 500, maxDelay: 2000 },
  certificateFile: undefined,
  privateKeyFile: undefined,
});

(async () => {
  try {
    console.log("Connecting with Sign+Basic256Sha256 to opc.tcp://10.240.240.31:4840 ...");
    await client.connect("opc.tcp://10.240.240.31:4840");
    console.log("Connected! Creating session...");
    const session = await client.createSession();
    console.log("Session created - PLC connection working!");
    await session.close();
    await client.disconnect();
  } catch(e) {
    console.error("FAILED:", e.message);
    if (e.message.includes("BadCertificate")) console.log("-> Certificate not trusted on PLC. Need to trust in PLCnext UI.");
    if (e.message.includes("BadSecurity")) console.log("-> Security policy rejected.");
    if (e.message.includes("BadTimeout") || e.message.includes("timeout")) console.log("-> Connection timed out.");
  }
})();
