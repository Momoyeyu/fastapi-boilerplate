class UserServiceError(Exception):
    pass


class UserAlreadyExistsError(UserServiceError):
    pass


class CreateUserFailedError(UserServiceError):
    pass


class InvalidCredentialsError(UserServiceError):
    pass
