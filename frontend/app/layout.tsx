import 'antd/dist/reset.css';
import '../styles/globals.css';
import React, {Fragment} from 'react';
import Facade from './components/facade'


export default function RootLayout({ children }: { children: React.ReactNode }) {
   
	return (
		<Fragment>
			<html lang="en">
				<head>
					<title>Landslides in the northern region</title>
				</head>
				<body>
					<Facade>
						{children}
					</Facade>
				</body>
			</html>
		</Fragment>
	);
}