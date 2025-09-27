'use client';

import React, {useEffect, Fragment, useState} from 'react';
import { Layout, Menu, Typography, Button, Row, Col } from 'antd';
const {Header, Content, Footer} = Layout;
import { API_BASE } from '../lib/api';
import { LogoutOutlined } from '@ant-design/icons';
import { useRouter, usePathname} from 'next/navigation';
import Link from 'next/link';


export default function Facade({ children }: { children: React.ReactNode }) {
	const [dataSelected, setDataSelected] = useState([]);
	const pathname = usePathname();
    const router = useRouter();
	const itemsMenu = [
		{ 
			key : 'rain',
			label : 'Rain',
		},
		{ 
			key : 'landslide',
			label : 'Landslide risk area',
		},
		{ 
			key : 'statistics-landslide',
			label : 'Statistics landslide',
		},
		{ 
			key : 'province-district',
			label : 'Province / District',
		},
	]

	async function onLogout() {
		await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
		window.location.href = '/login';
	}

	async function guard() {
		const res = await fetch(`${API_BASE}/me`, { credentials: 'include' });
		if (res.status === 401) {
			window.location.href = '/login';
		} else {
			setDataSelected([pathname.replace('/', '')])
		}
	}
	
    useEffect(() => {
		if(pathname != '/login') {
			guard();
		} else {
		}

	}, [pathname])

	const onClick = (e:any) => {
        router.push(e.key);
		setDataSelected([e.key])
    };

	return (
		<Fragment>
			{pathname == '/login' ? (
				<Fragment>
					{children}
				</Fragment>
			) : (
				<Layout>
					<Header className={`header-sticky`}>
						<Row className={`header-sticky-rows`} justify="center">
							<Col span={6}>
								<Link href={`/`}>
									<Typography.Title level={4} style={{ color: 'white', margin: 0}}>Landslides in the northern region</Typography.Title>
								</Link>
							</Col>
							<Col span={15}>
								<Row justify={`center`}>
									<Col span={24}>
										<Menu
											theme="dark"
											mode="horizontal"
											selectedKeys={dataSelected}
											items={itemsMenu}
											style={{minWidth: 0 }}
											onClick={onClick}
										/>
									</Col>
								</Row>
							</Col>
							<Col span={3} className="text-right">
								<Button icon={<LogoutOutlined />} onClick={onLogout}>Logout</Button>
							</Col>
						</Row>
					</Header>
					<Content className="content-block">
						<div
						style={{
							minHeight: 680,
						}}
						>
							{children}
						</div>
					</Content>
					<Footer className="footer-block">
						Mini Project 204721 DATA ENGINEERING
					</Footer>
				</Layout>
			)}
		</Fragment>
	);
}