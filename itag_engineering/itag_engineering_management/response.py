"""Standard API response envelope (roadmap Section 9.3 / Section 29)."""


def success(data=None, message=None):
	envelope = {"ok": True, "data": data}
	if message:
		envelope["message"] = message
	return envelope


def error(error_code, message, data=None):
	envelope = {"ok": False, "error_code": error_code, "message": message}
	if data is not None:
		envelope["data"] = data
	return envelope
